import sys
import os
import time

current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(os.path.dirname(current_dir))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

import html
import csv
import json
import heapq
import base64
import datetime
import shutil

from chaoscrypt.settings import (
    LOGFILES, LOG_DIR, TELEGRAM_AUTO_NOTIFY, ROOT_DIR, ASSETS_DIR,
    RANSOM_NOTE_NAME, RANSOM_QR_NAME, IMG_LOGO_REPORT, IMG_LOGO_SYSTEM,
    ALL_PHASES
)

try:
    from chaoscrypt.telegram_notify import send_document, send_message, send_photo
except ImportError:
    send_document = None
    send_message = None
    send_photo = None

REPORT_HTML = os.path.join(LOG_DIR, 'full_report.html')
REPORT_CSV  = os.path.join(LOG_DIR, 'full_report.csv')
REPORT_JSON = os.path.join(LOG_DIR, 'full_report.json')

DFIR_TIPS = {
    "encryption": "Check for backup keys, confirm their presence in logs before attempting recovery.",
    "infection": "Validate registry/task/autorun persistence, clear after remediation.",
    "chaos": "Teaching-phase effects, for user awareness analysis only.",
    "remediation": "After cleanup, verify registry/tasks and scan for remnants.",
    "race_detected": "Race condition! Split logs and targets per phase. Validate integrity.",
    "recovery": "After recovery confirm decrypted files, match key to folder.",
    "detection": "Monitor PID/path re-appearances, guard against process re-launch.",
    "dropper": "Tracks orchestrator/launcher events and cross-phase triggers.",
    "system_hooks": "Persistence, sandbox traces, registry, or system artifact events.",
    "network": "Exfiltration/C2/traffic observed by monitor.",
    "payment": "Ransom payment flow events, key delivery, wallet activity.",
    "exfiltration": "Data exfiltration detected, keys/credentials sent to C2.",
    "info": "Informational event, initialization or status update.",
    "finish": "Phase or pipeline completion event.",
}

IOC_ALERTS = {
    RANSOM_NOTE_NAME: "CRITICAL: Ransom note discovered. Hostile intent confirmed.",
    RANSOM_QR_NAME: "CRITICAL: Payment QR-code detected. Financial extortion in progress.",
}

PHASE_COLORS = {
    "system_hooks": "#6c5ce7",
    "dropper":      "#636e72",
    "network":      "#00b894",
    "c2":           "#e17055",
    "agent":        "#fdcb6e",
    "chaos":        "#d63031",
    "payment":      "#e84393",
    "show":         "#ff3333",
    "stealth":      "#0088ff",
    "antidote":     "#00ff88",
    "recovery":     "#00cec9",
}


def _load_theme():
    theme_path = os.path.join(ASSETS_DIR, "chaos_theme.json")
    if os.path.isfile(theme_path):
        try:
            with open(theme_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def _logo_base64(filename):
    path = os.path.join(ASSETS_DIR, filename)
    if not os.path.isfile(path):
        return ""
    try:
        with open(path, 'rb') as f:
            data = f.read()
        ext = os.path.splitext(filename)[1].lower()
        mime = {
            '.png': 'image/png',
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.ico': 'image/x-icon',
        }.get(ext, 'image/png')
        return f"data:{mime};base64,{base64.b64encode(data).decode()}"
    except Exception:
        return ""


def parse_ts(event):
    try:
        d = event['ts']
        if '+' in d:
            dt = datetime.datetime.fromisoformat(d.replace('Z', '+00:00'))
        else:
            dt = datetime.datetime.fromisoformat(d)
        return dt
    except Exception:
        return datetime.datetime.min.replace(tzinfo=datetime.timezone.utc)


def streamfile(filepath, phase):
    if not os.path.exists(filepath):
        return
    with open(filepath, 'r', encoding='utf-8') as jf:
        for idx, line in enumerate(jf):
            line = line.strip()
            if not line:
                continue
            try:
                ev = json.loads(line)
                ev['__logfile'] = phase
                yield ev
            except Exception:
                pass

def stream_merged_timeline(phases=ALL_PHASES):
    streams = []
    for ph in phases:
        logpth = LOGFILES.get(ph)
        if logpth:
            def _gen(logpth=logpth, ph=ph):
                for ev in streamfile(logpth, ph):
                    yield (parse_ts(ev), ev)
            streams.append(_gen())
    return [ev for _, ev in heapq.merge(*streams, key=lambda tup: tup[0])]


def build_streaming_summary_and_timeline(phases=ALL_PHASES):
    timeline = stream_merged_timeline(phases)
    summary = {ph: {
        "events": 0, "encryptions": 0, "recoveries": 0,
        "anomalies": 0, "keys_seen": set()
    } for ph in phases}
    race_count = 0
    incomplete_recoveries = 0
    encryption_missing_keys = 0

    for ev in timeline:
        ph = ev.get('phase')
        summary.setdefault(ph, {
            "events": 0, "encryptions": 0, "recoveries": 0,
            "anomalies": 0, "keys_seen": set()
        })
        summary[ph]["events"] += 1
        msg = ev.get('msg', '') or ''
        meta = ev.get('metadata') or {}

        if any(n in msg or n in str(meta.values())
               for n in (RANSOM_NOTE_NAME, RANSOM_QR_NAME)):
            ev['IOC'] = 1
            ev['tag'] = (ev.get('tag', '') or '') + ' IOC'
            if RANSOM_NOTE_NAME in msg or RANSOM_NOTE_NAME in str(meta.values()):
                ev['ioc_alert'] = IOC_ALERTS[RANSOM_NOTE_NAME]
            else:
                ev['ioc_alert'] = IOC_ALERTS[RANSOM_QR_NAME]

        if ev.get('event_type') == "encryption":
            summary[ph]["encryptions"] += 1
            k = meta.get('key')
            if k:
                summary[ph]["keys_seen"].add(k)
            else:
                encryption_missing_keys += 1

        if ev.get('event_type') == "recovery":
            summary[ph]["recoveries"] += 1
            rk = meta.get('key')
            if not rk:
                incomplete_recoveries += 1

        tag = ev.get('tag', '') or ''
        if "race" in tag:
            summary[ph]["anomalies"] += 1
            race_count += 1
        if "recommendation" in tag:
            summary[ph]["anomalies"] += 1

    for ph in summary:
        summary[ph]["keys_seen"] = (
            ", ".join(sorted(summary[ph]["keys_seen"]))
            if summary[ph]["keys_seen"] else ""
        )
    return summary, race_count, incomplete_recoveries, encryption_missing_keys, timeline


def report_streaming_html(timeline, summary, race_ct, incomplete_ct, misskey_ct, out_file=None):
    outp = out_file or REPORT_HTML
    theme = _load_theme()
    r = theme.get("report", {})

    logo_whitebg_b64 = _logo_base64(IMG_LOGO_REPORT)
    logo_dark_b64 = _logo_base64(IMG_LOGO_SYSTEM)

    logo_tag = ""
    if logo_whitebg_b64:
        logo_tag = f'<img src="{logo_whitebg_b64}" alt="ChaosCrypt" class="top-logo">'

    total_events = sum(s["events"] for s in summary.values())
    total_enc = sum(s["encryptions"] for s in summary.values())
    total_rec = sum(s["recoveries"] for s in summary.values())
    total_anom = sum(s["anomalies"] for s in summary.values())
    active_phases = sum(1 for s in summary.values() if s["events"] > 0)

    first_ts = ""
    last_ts = ""
    if timeline:
        first_ts = timeline[0].get('ts', '')[:19]
        last_ts = timeline[-1].get('ts', '')[:19]

    now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>ChaosCrypt DFIR Report</title>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{
    font-family: {r.get('title_font', "'Segoe UI', Consolas, sans-serif")};
    background: {r.get('body_bg', '#f4f4f4')};
    color: {r.get('body_fg', '#333')};
}}

/* HEADER */
.header {{
    background: {r.get('header_bg', '#fff')};
    border-bottom: {r.get('header_border_width', '4px')} solid {r.get('header_border', '#2a6ca2')};
    padding: 20px 30px;
    display: flex;
    align-items: center;
    justify-content: space-between;
}}
.header-left {{
    display: flex;
    align-items: center;
    gap: 15px;
}}
.top-logo {{ height: 70px; }}
.header-title {{
    font-size: 22px;
    font-weight: bold;
    color: {r.get('title_fg', '#333')};
}}
.header-subtitle {{
    font-size: 12px;
    color: #888;
    margin-top: 2px;
}}
.header-right {{
    text-align: right;
    font-size: 12px;
    color: #888;
}}

/* DASHBOARD */
.dashboard {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
    gap: 15px;
    padding: 20px 30px;
}}
.card {{
    background: #fff;
    border-radius: 8px;
    padding: 18px;
    text-align: center;
    box-shadow: {r.get('shadow', '0 2px 5px rgba(0,0,0,0.08)')};
    border-top: 3px solid #2a6ca2;
}}
.card.danger {{ border-top-color: #d63031; }}
.card.success {{ border-top-color: #00b894; }}
.card.warning {{ border-top-color: #fdcb6e; }}
.card-value {{
    font-size: 32px;
    font-weight: bold;
    color: #333;
    margin: 5px 0;
}}
.card-label {{
    font-size: 12px;
    color: #888;
    text-transform: uppercase;
    letter-spacing: 1px;
}}

/* CONTENT */
.content {{ padding: 10px 30px 30px; }}

/* PHASE SUMMARY */
.phase-grid {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
    gap: 12px;
    margin-bottom: 25px;
}}
.phase-card {{
    background: #fff;
    border-radius: 6px;
    padding: 14px;
    box-shadow: {r.get('shadow', '0 2px 5px rgba(0,0,0,0.08)')};
    border-left: 4px solid #2a6ca2;
}}
.phase-name {{
    font-weight: bold;
    font-size: 14px;
    text-transform: uppercase;
    margin-bottom: 6px;
}}
.phase-stat {{
    font-size: 12px;
    color: #666;
    font-family: Consolas, monospace;
}}

/* ALERTS */
.alert {{
    padding: 12px 18px;
    border-radius: 6px;
    margin-bottom: 15px;
    font-size: 13px;
}}
.alert-warning {{
    background: {r.get('warning_bg', '#ffecc7')};
    color: {r.get('warning_fg', '#ad8000')};
    border-left: 4px solid #f0ad4e;
}}
.alert-danger {{
    background: {r.get('ioc_bg', '#ffdddd')};
    color: {r.get('ioc_fg', '#990000')};
    border-left: 4px solid #d9534f;
}}

/* TABLE */
table {{
    border-collapse: collapse;
    width: 100%;
    background: {r.get('table_bg', '#fff')};
    box-shadow: {r.get('shadow', '0 2px 5px rgba(0,0,0,0.08)')};
    border-radius: 6px;
    overflow: hidden;
    margin-bottom: 25px;
}}
th {{
    background: {r.get('table_header_bg', '#2a6ca2')};
    color: {r.get('table_header_fg', '#fff')};
    padding: 12px 10px;
    text-align: left;
    font-size: 12px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}}
td {{
    border-bottom: 1px solid {r.get('table_border', '#ddd')};
    padding: 9px 10px;
    font-family: {r.get('table_font', 'Consolas, monospace')};
    font-size: {r.get('table_font_size', '12px')};
    max-width: 300px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}}
tr:nth-child(even) {{ background: {r.get('table_alt_row', '#f9f9f9')}; }}
tr:hover {{ background: #e8f4fd; }}
.ioc {{ background: {r.get('ioc_bg', '#ffdddd')} !important; }}
.ioc td {{ color: {r.get('ioc_fg', '#900')}; font-weight: bold; }}
.rec {{ color: {r.get('recommendation_fg', '#0066cc')}; font-weight: bold; }}

/* PHASE BADGES */
.badge {{
    display: inline-block;
    padding: 2px 8px;
    border-radius: 10px;
    font-size: 11px;
    font-weight: bold;
    color: #fff;
}}

/* FOOTER */
.footer {{
    text-align: center;
    padding: 20px;
    color: #aaa;
    font-size: 11px;
    border-top: 1px solid #ddd;
    margin-top: 30px;
}}
</style>
</head>
<body>

<!-- HEADER -->
<div class="header">
    <div class="header-left">
        {logo_tag}
        <div>
            <div class="header-title">ChaosCrypt DFIR: Forensic Timeline Report</div>
            <div class="header-subtitle">Automated Analysis &bull; Educational Ransomware Simulation</div>
        </div>
    </div>
    <div class="header-right">
        Generated: {now}<br>
        Timeline: {html.escape(first_ts)} &mdash; {html.escape(last_ts)}
    </div>
</div>

<!-- DASHBOARD -->
<div class="dashboard">
    <div class="card">
        <div class="card-label">Total Events</div>
        <div class="card-value">{total_events}</div>
    </div>
    <div class="card danger">
        <div class="card-label">Encryptions</div>
        <div class="card-value">{total_enc}</div>
    </div>
    <div class="card success">
        <div class="card-label">Recoveries</div>
        <div class="card-value">{total_rec}</div>
    </div>
    <div class="card warning">
        <div class="card-label">Anomalies</div>
        <div class="card-value">{total_anom}</div>
    </div>
    <div class="card">
        <div class="card-label">Active Phases</div>
        <div class="card-value">{active_phases}</div>
    </div>
    <div class="card danger">
        <div class="card-label">Race Conditions</div>
        <div class="card-value">{race_ct}</div>
    </div>
</div>

<div class="content">
"""

    if race_ct > 0:
        html_content += (
            f'<div class="alert alert-warning">'
            f'<strong>Warning:</strong> {race_ct} race condition(s) detected. '
            f'Review phase isolation.</div>\n'
        )
    if misskey_ct > 0:
        html_content += (
            f'<div class="alert alert-danger">'
            f'<strong>Alert:</strong> {misskey_ct} encryption(s) missing key in logs. '
            f'Recovery may be impossible for affected files.</div>\n'
        )
    if incomplete_ct > 0:
        html_content += (
            f'<div class="alert alert-warning">'
            f'<strong>Warning:</strong> {incomplete_ct} incomplete recovery event(s). '
            f'Verify file integrity.</div>\n'
        )

    html_content += '<h3 style="margin-bottom:12px;">Phase Summary</h3>\n'
    html_content += '<div class="phase-grid">\n'
    for ph, s in summary.items():
        if s["events"] == 0:
            continue
        color = PHASE_COLORS.get(ph, "#2a6ca2")
        keys_preview = s["keys_seen"][:20] + "..." if len(s["keys_seen"]) > 20 else s["keys_seen"]
        html_content += f"""<div class="phase-card" style="border-left-color:{color}">
    <div class="phase-name" style="color:{color}">{html.escape(ph)}</div>
    <div class="phase-stat">Events: {s['events']}</div>
    <div class="phase-stat">Encryptions: {s['encryptions']} | Recoveries: {s['recoveries']}</div>
    <div class="phase-stat">Anomalies: {s['anomalies']}</div>
    <div class="phase-stat">Keys: {html.escape(keys_preview) if keys_preview else 'none'}</div>
</div>\n"""
    html_content += '</div>\n'

    html_content += '<h3 style="margin-bottom:12px;">Full Event Timeline (UTC)</h3>\n'
    html_content += ('<table><tr>'
                     '<th>#</th><th>Time</th><th>Phase</th><th>Event</th>'
                     '<th>Message</th><th>Metadata</th><th>Tag</th>'
                     '<th>DFIR Tip</th><th>IOC</th></tr>\n')

    def safe(val):
        return html.escape("" if val is None else str(val))

    for idx, ev in enumerate(timeline, 1):
        meta_str = "; ".join(
            f"{safe(k)}={safe(v)}"
            for k, v in (ev.get('metadata') or {}).items()
        )
        tip = DFIR_TIPS.get(ev.get("event_type"), "")
        ioc = safe(ev.get('ioc_alert', '')) if ev.get('IOC') else ""
        phase = ev.get('phase', '')
        color = PHASE_COLORS.get(phase, '#888')
        badge = f'<span class="badge" style="background:{color}">{safe(phase)}</span>'
        cls = " class='ioc'" if ev.get('IOC') else ""

        html_content += (
            f"<tr{cls}>"
            f"<td>{idx}</td>"
            f"<td>{safe(ev.get('ts', ''))[:19]}</td>"
            f"<td>{badge}</td>"
            f"<td>{safe(ev.get('event_type', ''))}</td>"
            f"<td>{safe(ev.get('msg', ''))}</td>"
            f"<td title=\"{safe(meta_str)}\">{safe(meta_str[:80])}</td>"
            f"<td>{safe(ev.get('tag', ''))}</td>"
            f"<td>{safe(tip)}</td>"
            f"<td>{ioc}</td>"
            f"</tr>\n"
        )

    html_content += "</table>\n"

    html_content += f"""
</div>
<div class="footer">
    ChaosCrypt v3.0 &bull; Educational Ransomware Simulation &bull; DFIR Forensic Report<br>
    Generated {now} &bull; {total_events} events across {active_phases} phases
</div>
</body></html>"""

    with open(outp, 'w', encoding='utf-8') as f:
        f.write(html_content)
    return outp

def report_streaming_csv(timeline, out_file=None):
    keys = ["ts", "phase", "event_type", "msg", "tag", "metadata", "source", "recommendation"]
    outp = out_file or REPORT_CSV
    with open(outp, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=keys)
        writer.writeheader()
        for ev in timeline:
            row = {k: ev.get(k, "") for k in keys}
            if isinstance(row['metadata'], dict):
                row['metadata'] = "; ".join(f"{k}={v}" for k, v in row['metadata'].items())
            writer.writerow(row)
    return outp

def report_streaming_json(timeline, out_file=None):
    outp = out_file or REPORT_JSON
    with open(outp, 'w', encoding='utf-8') as f:
        json.dump(timeline, f, ensure_ascii=False, indent=2)
    return outp


def generate_reports_only():
    print("[AutoAnalyzer] Generating reports (no TG)...")
    summary, race_ct, incomplete_ct, misskey_ct, timeline = build_streaming_summary_and_timeline()
    html_path = report_streaming_html(timeline, summary, race_ct, incomplete_ct, misskey_ct)
    print(f"[+] HTML: {html_path}")
    csv_path = report_streaming_csv(timeline)
    print(f"[+] CSV: {csv_path}")
    json_path = report_streaming_json(timeline)
    print(f"[+] JSON: {json_path}")
    print("[AutoAnalyzer] Files ready.")
    return html_path, csv_path, json_path


def main_pipeline():
    html_path, csv_path, json_path = generate_reports_only()
    if not TELEGRAM_AUTO_NOTIFY:
        print("[TG] Auto-notify DISABLED.")
        return html_path, csv_path, json_path
    if not send_document:
        print("[TG] send_document not available.")
        return html_path, csv_path, json_path
    for ftype, path in [("HTML", html_path), ("CSV", csv_path), ("JSON", json_path)]:
        if os.path.isfile(path):
            try:
                status = send_document(path, caption=f"ChaosCrypt DFIR: Timeline ({ftype})", async_mode=False)
                print(f"[TG] {ftype}: {status}")
                time.sleep(2)
            except Exception as e:
                print(f"[TG] {ftype} failed: {e}")
    if send_message:
        send_message("✅ ChaosCrypt DFIR: Reports delivered!", async_mode=False)
    return html_path, csv_path, json_path

if __name__ == "__main__":
    main_pipeline()