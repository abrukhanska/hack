import os
import sys
import time
import subprocess

# ГАРАНТІЯ ІМПОРТІВ незалежно від location demo_launcher.py
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.append(parent_dir)

from chaoscrypt.settings import ROOT_DIR, LOG_DIR, TELEGRAM_AUTO_NOTIFY
try:
    from chaoscrypt.telegram_notify import send_message, send_document
except ImportError:
    send_message = None
    send_document = None
try:
    from chaoscrypt.modes.auto_analyzer import REPORT_HTML
except ImportError:
    REPORT_HTML = os.path.join(LOG_DIR, "full_report.html")

LAUNCH_ORDER = [
    ("show_case",     "Show phase"),
    ("stealth_case",  "Stealth phase"),
    ("antidote",      "Antidote (BlueTeam)"),
    ("auto_analyzer", "DFIR Analyzer/Timeline"),
]
MODES_DIRS = [
    os.path.join(ROOT_DIR, "chaoscrypt", "modes"),
    os.path.join(ROOT_DIR, "chaoscrypt")
]

def find_phase_script(phase):
    for d in MODES_DIRS:
        path = os.path.join(d, phase + ".py")
        if os.path.isfile(path):
            return path
    return None

PHASE_MODULES = {k: find_phase_script(k) for k, _ in LAUNCH_ORDER}

def phase_runner(modpath, phase_desc):
    abspath = os.path.abspath(modpath)
    if not os.path.isfile(abspath):
        msg = f"[DEMO] ❌ Phase '{phase_desc}' not found: {abspath}"
        print(msg)
        if send_message:
            send_message(msg, async_mode=False)
        return False
    msg = f"[DEMO] ▶️ {phase_desc} started!"
    print(msg)
    if send_message:
        send_message(msg, async_mode=True)
    env = os.environ.copy()
    orig_pythonpath = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = ROOT_DIR + (os.pathsep + orig_pythonpath if orig_pythonpath else "")
    try:
        ret = subprocess.run([sys.executable, abspath], env=env, check=False)
        msg2 = (f"[DEMO] ✅ {phase_desc} done." if ret.returncode == 0
                else f"[DEMO] ⚠️ {phase_desc} failed! (rc={ret.returncode})")
        print(msg2)
        if send_message:
            send_message(msg2, async_mode=False)
        return ret.returncode == 0
    except Exception as e:
        errmsg = f"[DEMO] ❌ Phase '{phase_desc}' crashed: {e}"
        print(errmsg)
        if send_message:
            send_message(errmsg, async_mode=False)
        return False

def launch_pipeline():
    print(f"[DEMO] LOG_DIR: {os.path.abspath(LOG_DIR)}")
    phase_results = []
    for phase_mod, phase_desc in LAUNCH_ORDER:
        ok = phase_runner(PHASE_MODULES[phase_mod], phase_desc)
        phase_results.append({"name": phase_mod, "desc": phase_desc, "ok": ok})
        time.sleep(1)  # wow-delay TG
    print("[DEMO] All phases complete!\nResults:")
    text_summary = []
    for r in phase_results:
        line = f"- {r['desc']}: {'OK' if r['ok'] else 'FAIL'}"
        print(line)
        text_summary.append(line)
    if send_message:
        summary_str = "[DEMO] 🏁 All phases finished:\n" + "\n".join(text_summary)
        send_message(summary_str, async_mode=False)
    auto_an_ok = next((r for r in phase_results if r['name'] == "auto_analyzer"), None)
    if auto_an_ok and auto_an_ok["ok"] and send_document and os.path.isfile(REPORT_HTML):
        try:
            send_document(REPORT_HTML, caption="ChaosCrypt Demo: Timeline (HTML)", async_mode=False)
        except Exception as e:
            if send_message:
                send_message(f"[DEMO] ⚠️ TG timeline report send failed: {e}", async_mode=False)

if __name__ == "__main__":
    print("=== ChaosCrypt DEMO LAUNCHER ===")
    if TELEGRAM_AUTO_NOTIFY:
        print("TG notify is ON! Telegram will be wow-bombed 😊")
    else:
        print("TG integration OFF (edit .env and settings.py for WOW!)")
    launch_pipeline()
    print("=== DEMO COMPLETE ===")