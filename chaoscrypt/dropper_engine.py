import os
import sys
import json
import argparse
import datetime
import subprocess
import time
import traceback

current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.append(parent_dir)

from chaoscrypt.settings import (
    ROOT_DIR, LOG_DIR, TELEGRAM_AUTO_NOTIFY, LOGFILES, ASSETS_DIR, IMG_LOGO_REPORT
)
from chaoscrypt.logbook import LogBook

try:
    from chaoscrypt.telegram_notify import send_message, send_photo, send_document
except ImportError:
    send_message = None
    send_photo = None
    send_document = None

try:
    from chaoscrypt.modes.auto_analyzer import generate_reports_only
    print("[DROP] auto_analyzer imported OK")
except Exception as e:
    generate_reports_only = None
    print(f"[DROP] Import auto_analyzer FAILED: {e}")

DROP_LOG_PHASE = "dropper"
MANIFEST_PATH = os.path.join(LOG_DIR, "demo_manifest.json")
REPORT_HTML_PATH = os.path.join(LOG_DIR, "full_report.html")

PHASES = [
    ("system_hooks", "🪝 System Hooks (Dropper/Persistence)"),
    ("network_monitor", "📡 Network Monitor (Exfil/C2 demo)"),
    ("c2_commander", "🎯 C2 Commander (Exfil/Recon/Beacon)"),
    ("file_agent", "🕵️ File Agent (Integrity/Watermark)"),
    ("chaos_effects", "🎭 Chaos Effects (Visual/Teaching)"),
    ("show_case", "🟢 Show phase (Ransomware)"),
    ("stealth_case", "🔵 Stealth phase (Persistence)"),
    ("payment_flow", "💰 Payment Flow (Ransom/Key Delivery)"),
    ("antidote", "🛡️ Antidote (BlueTeam Cleanup)"),
    ("auto_analyzer", "📊 DFIR Analyzer / Timeline"),
]

logbook = LogBook(phase=DROP_LOG_PHASE)

def log_drop_event(event_type, msg, extra=None):
    logbook.log_event(event_type, msg, metadata=extra)

def find_phase_script(phase_name):
    candidates = [
        os.path.join(ROOT_DIR, "chaoscrypt", "modes", f"{phase_name}.py"),
        os.path.abspath(os.path.join(os.path.dirname(__file__), f"{phase_name}.py")),
        os.path.abspath(f"{phase_name}.py"),
        os.path.join(ROOT_DIR, "chaoscrypt", f"{phase_name}.py"),
        os.path.join(ROOT_DIR, f"{phase_name}.py")
    ]
    for path in candidates:
        if os.path.isfile(path):
            return path
    return None

def run_phase(phase_name, phase_desc):
    print(f"\n[DEBUG] ===== Preparing to launch phase: {phase_name} =====")

    # === NUCLEAR OPTION: auto_analyzer inline ===
    if phase_name == "auto_analyzer":
        if generate_reports_only is None:
            print("[DROP] ❌ auto_analyzer not imported, skipping.")
            return {"name": phase_name, "desc": phase_desc, "ok": False,
                    "time": datetime.datetime.now(datetime.timezone.utc).isoformat()}

        print("[DROP] ▶️ auto_analyzer (INLINE Nuclear Option)...")
        try:
            html_path, csv_path, json_path = generate_reports_only()
            print(f"[DROP] Reports: HTML={os.path.isfile(html_path)} CSV={os.path.isfile(csv_path)} JSON={os.path.isfile(json_path)}")

            if send_document:
                for ftype, path in [("HTML", html_path), ("CSV", csv_path), ("JSON", json_path)]:
                    if os.path.isfile(path):
                        print(f"[DROP] 📤 Sending {ftype}: {path}")
                        try:
                            status = send_document(path, caption=f"ChaosCrypt DFIR ({ftype})", async_mode=False)
                            print(f"[DROP] TG {ftype}: {status}")
                            time.sleep(2)
                        except Exception as e:
                            print(f"[DROP] TG {ftype} EXCEPTION: {e}")
                    else:
                        print(f"[DROP] {ftype} missing: {path}")
                if send_message:
                    send_message("✅ DFIR Reports delivered!", async_mode=False)
            else:
                print("[DROP] send_document is None!")

            print("[DROP] ✅ auto_analyzer done!")
            return {"name": phase_name, "desc": phase_desc, "ok": True,
                    "time": datetime.datetime.now(datetime.timezone.utc).isoformat()}
        except Exception as e:
            print(f"[DROP] ❌ auto_analyzer FAILED: {e}")
            traceback.print_exc()
            return {"name": phase_name, "desc": phase_desc, "ok": False,
                    "time": datetime.datetime.now(datetime.timezone.utc).isoformat()}

    abspath = find_phase_script(phase_name)
    if not abspath:
        msg = f"[DROP] ❌ Phase '{phase_desc}' not found!"
        print(msg)
        log_drop_event("notfound", msg, {"phase_name": phase_name})
        return {"name": phase_name, "desc": phase_desc, "ok": False,
                "time": datetime.datetime.now(datetime.timezone.utc).isoformat()}

    print(f"[DROP] ▶️ {phase_desc} started!")
    log_drop_event("start", f"{phase_desc} started", {"path": abspath})

    if send_message:
        send_message(f"▶️ <b>{phase_desc}</b> started", parse_mode="HTML", async_mode=True)

    env = os.environ.copy()
    orig_pythonpath = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = ROOT_DIR + (os.pathsep + orig_pythonpath if orig_pythonpath else "")
    env["CHAOSCRYPT_DROPPER_PID"] = str(os.getpid())

    timeout_sec = 120
    if phase_name == "file_agent":
        phase_timeout = 8
    elif phase_name == "antidote":
        phase_timeout = 60
    elif phase_name == "c2_commander":
        phase_timeout = 90
    elif phase_name == "chaos_effects":
        phase_timeout = 90
    elif phase_name == "payment_flow":
        phase_timeout = 120
    else:
        phase_timeout = timeout_sec

    cwd_dir = os.path.dirname(abspath)
    t0 = time.time()

    try:
        ret = subprocess.run([sys.executable, abspath], env=env, cwd=cwd_dir, check=False, timeout=phase_timeout)
        ok = ret.returncode == 0
        duration = time.time() - t0
        icon = "✅" if ok else "⚠️"
        msg2 = f"[DROP] {icon} {phase_desc} done ({duration:.1f}s)."
        print(msg2)
        log_drop_event("finish" if ok else "fail", msg2, {"phase_name": phase_name, "rc": ret.returncode})
        return {"name": phase_name, "desc": phase_desc, "ok": ok,
                "time": datetime.datetime.now(datetime.timezone.utc).isoformat()}
    except subprocess.TimeoutExpired:
        print(f"[DROP] ⚠️ {phase_desc} TIMEOUT ({phase_timeout}s), moving on.")
        log_drop_event("timeout", f"{phase_desc} TIMEOUT", {"phase_name": phase_name})
        return {"name": phase_name, "desc": phase_desc, "ok": True,
                "time": datetime.datetime.now().isoformat()}
    except Exception as e:
        print(f"[DROP] ❌ Phase '{phase_desc}' crashed: {e}")
        traceback.print_exc()
        log_drop_event("fail", str(e), {"phase_name": phase_name})
        return {"name": phase_name, "desc": phase_desc, "ok": True,
                "time": datetime.datetime.now().isoformat()}

def save_manifest(manifest):
    os.makedirs(LOG_DIR, exist_ok=True)
    try:
        with open(MANIFEST_PATH, 'w', encoding='utf-8') as mf:
            json.dump(manifest, mf, indent=2)
    except Exception as e:
        log_drop_event("error", "Manifest write error", {"error": str(e)})

def run_demo_phases(selected_phases=None, fail_fast=False):
    if send_photo:
        logo_path = os.path.join(ASSETS_DIR, IMG_LOGO_REPORT)
        if os.path.exists(logo_path):
            try:
                send_photo(logo_path, caption="🚀 <b>ChaosCrypt Engine Initiated</b>", parse_mode="HTML",
                           async_mode=True)
            except Exception:
                pass

    manifest = {
        "started": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "phases": [],
        "user": os.getenv("USER") or os.getenv("USERNAME") or "unknown"
    }

    phases_to_run = selected_phases or PHASES
    for phase_idx, (phase_name, phase_desc) in enumerate(phases_to_run):
        print(f"\n[DEBUG] ===== PHASE {phase_idx+1}/{len(phases_to_run)}: {phase_name} =====")
        phase_info = run_phase(phase_name, phase_desc)
        print(f"[DEBUG] Result: {phase_info}")
        manifest["phases"].append(phase_info)
        save_manifest(manifest)
        if fail_fast and not phase_info.get('ok', False):
            remaining = [n for n, _ in phases_to_run[phase_idx+1:]]
            if "auto_analyzer" not in remaining:
                print("[DROP] Critical fail, stopping pipeline.")
                break
            else:
                print("[DROP] Fail but auto_analyzer pending, continuing...")
        time.sleep(1.5)

    manifest["finished"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    save_manifest(manifest)

    print("\n" + "=" * 60)
    print("[DROP] Pipeline Finished.")
    print(f"[DROP] Manifest: {MANIFEST_PATH}")
    if send_message:
        send_message("🏁 <b>Simulation Complete.</b> All artifacts secured.", parse_mode="HTML", async_mode=False)

def run_single_phase(phase_name):
    desc = next((d for n, d in PHASES if n == phase_name), f"Custom run: {phase_name}")
    run_phase(phase_name, desc)

def main():
    parser = argparse.ArgumentParser(description="ChaosCrypt Dropper Engine")
    parser.add_argument('--phase', type=str, help="Run specific phase")
    parser.add_argument('--failfast', action="store_true", help="Stop on error")
    args = parser.parse_args()

    print("=== ChaosCrypt DROPPER ENGINE (Diamond Edition) ===")
    if args.phase:
        run_single_phase(args.phase)
    else:
        run_demo_phases(fail_fast=args.failfast)
    print("=== DROPPER COMPLETE ===")

if __name__ == "__main__":
    main()