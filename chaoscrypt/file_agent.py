import os
import sys
import time
import shutil
import threading
import hashlib

# DRY patch for imports anywhere
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.append(parent_dir)

from chaoscrypt.settings import (
    ASSETS_DIR, LOGFILES, TXT_LOGS, IMG_LOGO_SYSTEM, IMG_SUCCESS, LOG_DIR,
    ALL_PHASES
)
from chaoscrypt.logbook import LogBook

try:
    from chaoscrypt.telegram_notify import send_message, send_photo
except ImportError:
    send_message = None
    send_photo = None

# === Фазова константа для цього агента
AGENT_PHASE = "agent"  # Додати цей ключ у settings.py

# === Константи для wow/teach/DFIR
WATCH_TARGET_DIR = os.environ.get("WATCH_TARGET_DIR") or os.path.join(LOG_DIR, "../Target_Watched")
os.makedirs(WATCH_TARGET_DIR, exist_ok=True)
WATCH_DELAY_SEC = 2.5    # Період сканування (wow demonstration)

def hash_file(filepath):
    """Для демонстрації/DFIR: отримує sha256 хеш для wow-звіту."""
    h = hashlib.sha256()
    try:
        with open(filepath, "rb") as f:
            while True:
                chunk = f.read(65536)
                if not chunk:
                    break
                h.update(chunk)
        return h.hexdigest()
    except Exception:
        return "-ERR-"

def wow_drop_logo(folder, logbook):
    """Копіює wow-лого у цільову (моніторену) папку для teach/watermark."""
    src_logo = os.path.join(ASSETS_DIR, IMG_LOGO_SYSTEM)
    dst_logo = os.path.join(folder, "ZZZ_AGENT_WOW_MARKER.png")
    if os.path.exists(src_logo):
        shutil.copy2(src_logo, dst_logo)
        logbook.log_event("agent", f"Wow-marker logo dropped to: {dst_logo}")
        return dst_logo
    return None

def agent_watch_loop(logbook, stop_event=None):
    """Wow-DFIR file agent loop моніторить створення/видалення/змінення. Ллє все у wow лог"""
    print(f"[AGENT] Watching directory: {WATCH_TARGET_DIR}")
    logbook.log_event("info", f"Agent started, watching: {WATCH_TARGET_DIR}")

    prev_snapshot = {}
    while not (stop_event and stop_event.is_set()):
        curr_snapshot = {}
        try:
            for fname in os.listdir(WATCH_TARGET_DIR):
                fpath = os.path.join(WATCH_TARGET_DIR, fname)
                if os.path.isfile(fpath):
                    stat = os.stat(fpath)
                    curr_snapshot[fname] = (stat.st_size, stat.st_mtime)
        except Exception as e:
            logbook.log_event("error", f"Failed to scan folder: {e}")

        # === Wow: created
        for fname in curr_snapshot.keys() - prev_snapshot.keys():
            fpath = os.path.join(WATCH_TARGET_DIR, fname)
            h = hash_file(fpath)
            logbook.log_event("file_create", f"New file: {fname}", metadata={"sha256": h, "size": curr_snapshot[fname][0]})
            # Special: якщо це спеціальний wow-файл, тригер дропу логотипа!
            if fname.lower().endswith(".flag") or fname.lower().startswith("wow_"):
                marker_path = wow_drop_logo(WATCH_TARGET_DIR, logbook)
                if send_photo and marker_path and os.path.exists(marker_path):
                    send_photo(marker_path, caption=f"📦 Wow-agent: Detected marker '{fname}'. Logo dropped!", async_mode=False)

        # === Wow: deleted
        for fname in prev_snapshot.keys() - curr_snapshot.keys():
            logbook.log_event("file_delete", f"Deleted file: {fname}")

        # === Changed
        for fname in curr_snapshot.keys() & prev_snapshot.keys():
            if curr_snapshot[fname][1] != prev_snapshot[fname][1]:
                h = hash_file(os.path.join(WATCH_TARGET_DIR, fname))
                logbook.log_event("file_modify", f"File modified: {fname}", metadata={"sha256": h, "size": curr_snapshot[fname][0]})

        prev_snapshot = curr_snapshot
        time.sleep(WATCH_DELAY_SEC)

def run_agent_once():
    stop_event = threading.Event()
    logbook = LogBook(phase=AGENT_PHASE)
    t = threading.Thread(target=agent_watch_loop, args=(logbook, stop_event), daemon=True)
    t.start()
    print("[AGENT] Running in background (press Ctrl+C to exit)")
    try:
        while True:
            time.sleep(3)
    except KeyboardInterrupt:
        print("\n[AGENT] Stopping...")
        stop_event.set()
        t.join(timeout=2)
    logbook.log_event("info", "Agent stopped")
    logbook.close()
    print("[AGENT] Done.")

if __name__ == "__main__":
    run_agent_once()