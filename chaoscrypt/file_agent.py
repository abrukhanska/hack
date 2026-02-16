import os
import sys
import time
import shutil
import threading
import hashlib

current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(os.path.dirname(current_dir))
if parent_dir not in sys.path:
    sys.path.append(parent_dir)

from chaoscrypt.settings import (
    ASSETS_DIR, IMG_LOGO_SYSTEM, IMG_SUCCESS,
    WATCH_TARGET_DIR, SHOW_TARGET_DIR, STEALTH_TARGET_DIR,
    LOG_DIR
)
from chaoscrypt.logbook import LogBook

try:
    from chaoscrypt.telegram_notify import send_message, send_photo
except ImportError:
    send_message = None
    send_photo = None

AGENT_PHASE = "agent"
WATCH_DELAY_SEC = 2.5


def hash_file(filepath):
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
    src_logo = os.path.join(ASSETS_DIR, IMG_LOGO_SYSTEM)
    dst_logo = os.path.join(folder, "ZZZ_AGENT_WOW_MARKER.png")
    if os.path.exists(src_logo):
        shutil.copy2(src_logo, dst_logo)
        logbook.log_event("agent", f"Wow-marker logo dropped to: {dst_logo}")
        return dst_logo
    return None


def scan_targets(logbook):
    targets_found = []
    for label, target_dir in [("Show", SHOW_TARGET_DIR), ("Stealth", STEALTH_TARGET_DIR)]:
        if not os.path.isdir(target_dir):
            continue
        for fname in os.listdir(target_dir):
            fpath = os.path.join(target_dir, fname)
            if os.path.isfile(fpath):
                h = hash_file(fpath)
                size = os.path.getsize(fpath)
                targets_found.append({
                    "file": fname,
                    "path": fpath,
                    "phase": label.lower(),
                    "size": size,
                    "sha256": h,
                })
                logbook.log_event("detection", f"Target found: {fname}",
                                  metadata={"path": fpath, "size": size,
                                            "sha256": h, "target": label})
    return targets_found


def agent_watch_loop(logbook, stop_event=None):
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

        for fname in curr_snapshot.keys() - prev_snapshot.keys():
            fpath = os.path.join(WATCH_TARGET_DIR, fname)
            h = hash_file(fpath)
            logbook.log_event("file_create", f"New file: {fname}",
                              metadata={"sha256": h, "size": curr_snapshot[fname][0]})
            if fname.lower().endswith(".flag") or fname.lower().startswith("wow_"):
                marker_path = wow_drop_logo(WATCH_TARGET_DIR, logbook)
                if send_photo and marker_path and os.path.exists(marker_path):
                    send_photo(marker_path,
                               caption=f"Wow-agent: Detected marker '{fname}'. Logo dropped!",
                               async_mode=False)

        for fname in prev_snapshot.keys() - curr_snapshot.keys():
            logbook.log_event("file_delete", f"Deleted file: {fname}")

        # Modified
        for fname in curr_snapshot.keys() & prev_snapshot.keys():
            if curr_snapshot[fname][1] != prev_snapshot[fname][1]:
                h = hash_file(os.path.join(WATCH_TARGET_DIR, fname))
                logbook.log_event("file_modify", f"File modified: {fname}",
                                  metadata={"sha256": h, "size": curr_snapshot[fname][0]})
        prev_snapshot = curr_snapshot
        time.sleep(WATCH_DELAY_SEC)


def run_agent_once():
    logbook = LogBook(phase=AGENT_PHASE)

    print("[AGENT] Scanning target directories...")
    targets = scan_targets(logbook)
    print(f"[AGENT] Found {len(targets)} target files.")

    if send_message and targets:
        files_list = "\n".join(
            f"  {t['file']} ({t['size']} bytes)"
            for t in targets[:10]
        )
        send_message(
            f"<b>File Agent: Target Scan</b>\n"
            f"<code>Targets: {len(targets)} files\n{files_list}</code>",
            parse_mode="HTML", async_mode=True
        )

    stop_event = threading.Event()
    t = threading.Thread(target=agent_watch_loop, args=(logbook, stop_event), daemon=True)
    t.start()
    print("[AGENT] Watching in background (press Ctrl+C to exit)")
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