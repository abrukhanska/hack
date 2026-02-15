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
import datetime
import shutil

from chaoscrypt.settings import (
    LOGFILES, LOG_DIR, TELEGRAM_AUTO_NOTIFY, ROOT_DIR, ASSETS_DIR,
    RANSOM_NOTE_NAME, RANSOM_QR_NAME, IMG_LOGO_REPORT, ALL_PHASES
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
    "network": "Exfiltration/C2/traffic observed by monitor."
}

IOC_ALERTS = {
    RANSOM_NOTE_NAME: "CRITICAL: Ransom note discovered. Hostile intent confirmed.",
    RANSOM_QR_NAME: "CRITICAL: Payment QR-code detected. Financial extortion in progress."
}

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
    if not os.path.exists(filepath): return
    with open(filepath, 'r', encoding='utf-8') as jf:
        for idx, line in enumerate(jf):
            line = line.strip()
            if not line: continue
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
    summary = {ph: {"events": 0, "encryptions": 0, "recoveries": 0, "anomalies": 0, "keys_seen": set()} for ph in phases}
    race_count = 0
    incomplete_recoveries = 0
    encryption_missing_keys = 0
    for ev in timeline:
        ph = ev.get('phase')
        summary.setdefault(ph, {"events": 0, "encryptions": 0, "recoveries": 0, "anomalies": 0, "keys_seen": set()})
        summary[ph]["events"] += 1
        msg = ev.get('msg', '') or ''
        meta = ev.get('metadata') or {}
        if any(n in msg or n in str(meta.values()) for n in (RANSOM_NOTE_NAME, RANSOM_QR_NAME)):
            ev['IOC'] = 1
            ev['tag'] = (ev.get('tag', '') or '') + ' IOC'
            ev['ioc_alert'] = IOC_ALERTS[RANSOM_NOTE_NAME if RANSOM_NOTE_NAME in msg or RANSOM_NOTE_NAME in str(meta.values()) else RANSOM_QR_NAME]
        if ev.get('event_type') == "encryption":
            summary[ph]["encryptions"] += 1
            k = meta.get('key')
            if k: summary[ph]["keys_seen"].add(k)
            else: encryption_missing_keys += 1
        if ev.get('event_type') == "recovery":
            summary[ph]["recoveries"] += 1
            rk = meta.get('key')
            if not rk: incomplete_recoveries += 1
        if (ev.get('tag', '') or '') and "race" in (ev.get('tag', '') or ''):
            summary[ph]["anomalies"] += 1
            race_count += 1
        if (ev.get('tag', '') or '') and "recommendation" in (ev.get('tag', '') or ''):
            summary[ph]["anomalies"] += 1
    for ph in summary:
        summary[ph]["keys_seen"] = ", ".join(sorted(summary[ph]["keys_seen"])) if summary[ph]["keys_seen"] else ""
    return summary, race_count, incomplete_recoveries, encryption_missing_keys, timeline

def report_streaming_html(timeline, summary, race_ct, incomplete_ct, misskey_ct, out_file=None):
    outp = out_file or REPORT_HTML
    logo_src = os.path.join(ASSETS_DIR, IMG_LOGO_REPORT)
    logo_dst = os.path.join(LOG_DIR, IMG_LOGO_REPORT)
    img_tag = ""
    if os.path.exists(logo_src):
        try:
            shutil.copy2(logo_src, logo_dst)
            img_tag = f'<img src="{html.escape(IMG_LOGO_REPORT)}" alt="ChaosCrypt Logo" class="top-logo">'
        except Exception:
            pass
    html_top = (
        "<html><head><meta charset='utf-8'><style>"
        "body{font-family: 'Segoe UI', Consolas, sans-serif; background:#f4f4f4; color:#333; margin:0; padding:0;}"
        ".header-bar {background: #fff; padding: 20px; border-bottom: 4px solid #2a6ca2; display: flex; align-items: center; justify-content: space-between;}"
        ".top-logo {height: 80px;}"
        ".report-title {font-size: 24px; font-weight: bold; color: #333;}"
        ".content {padding: 20px;}"
        "table{border-collapse:collapse;width:100%;margin-bottom:25px; background: white; box-shadow: 0 2px 5px rgba(0,0,0,0.08);}"
        "th{background-color:#2a6ca2; color:white; padding:12px; text-align:left;}"
        "td{border-bottom:1px #ddd solid;padding:10px; font-family: Consolas, monospace; font-size: 13px;}"
        "tr:nth-child(even){background:#f9f9f9;}"
        ".ioc{background:#ffdddd; color:#900; font-weight: bold;}"
        ".rec{color:#0066cc; font-weight:bold;}"
        ".err{background:#ffecc7; color:#ad8000; font-weight:bold; padding:8px; margin-top:8px;}"
        "</style></head><body>"
        f'<div class="header-bar"><div class="report-title">🛡️ ChaosCrypt Ultra: Forensic Timeline Report</div>{img_tag}</div>'
        "<div class='content'><h3>Executive Summary:</h3><ul>"
    )
    for ph, s in summary.items():
        html_top += ("<li><b>{}</b>: {} events, {} encryptions, {} recoveries, "
                     "anomalies: {}, keys seen: {}</li>".format(
                         html.escape(ph), s["events"], s["encryptions"], s["recoveries"],
                         s["anomalies"], html.escape(str(s["keys_seen"]))
                     ))
    html_top += "</ul>"
    html_top += (f"<div class='err'>"
                 f"Race conditions: {race_ct} | Incomplete recoveries: {incomplete_ct} | "
                 f"Encryptions missing key: {misskey_ct}</div>")
    html_top += ("<hr><h3>FULL Timeline of events (streamed, UTC)</h3>"
                 "<table><tr><th>Time (UTC)</th><th>Phase</th><th>EventType</th><th>Message</th><th>Meta</th>"
                 "<th>Tag</th><th>Recommendation</th><th>DFIR Tip</th><th>IOC</th></tr>")
    def safe_html(val):
        return html.escape("" if val is None else str(val))
    html_end = "</table></div></body></html>"
    with open(outp, 'w', encoding='utf-8') as f:
        f.write(html_top)
        for ev in timeline:
            meta = "; ".join(safe_html(k) + "=" + safe_html(v) for k, v in (ev.get('metadata') or {}).items())
            rec = (f"<span class='rec'>{safe_html(ev.get('recommendation', ''))}</span>"
                   if ev.get("recommendation") else "")
            tip = DFIR_TIPS.get(ev.get("event_type"), "")
            ioc = (f"<span class='ioc'>{safe_html(ev.get('ioc_alert', ''))}</span>" if ev.get('IOC') else "")
            row = (
                "<tr{cls}><td>{ts}</td><td>{phase}</td><td>{event_type}</td><td>{msg}</td><td>{meta}</td>"
                "<td>{tag}</td><td>{rec}</td><td>{tip}</td><td>{ioc}</td></tr>\n"
            ).format(
                ts=safe_html(ev.get('ts', "")),
                phase=safe_html(ev.get('phase', "")),
                event_type=safe_html(ev.get('event_type', "")),
                msg=safe_html(ev.get('msg', "")),
                meta=meta,
                tag=safe_html(ev.get('tag', "")),
                rec=rec,
                tip=safe_html(tip),
                ioc=ioc,
                cls=" class='ioc'" if ev.get('IOC') else ""
            )
            f.write(row)
        f.write(html_end)
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
    """Тільки генерація файлів, БЕЗ TG"""
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
    """Повний запуск: генерація + TG (для ручного запуску)"""
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