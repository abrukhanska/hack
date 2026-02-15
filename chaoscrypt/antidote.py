import os
import sys
import json
import shutil
import psutil
import time
import hashlib

current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.append(parent_dir)

try:
    import winreg
    HAS_WINREG = True
except ImportError:
    HAS_WINREG = False

from chaoscrypt.settings import (
    LOGFILES, LOG_DIR, QUARANTINE_DIR, SHOW_TARGET_DIR, STEALTH_TARGET_DIR,
    ENCRYPTED_SUFFIX, METADATA_SUFFIX, BACKUP_SUFFIX, TMP_SUFFIX,
    RANSOM_NOTE_NAME, RANSOM_QR_NAME, WATCH_TARGET_DIR
)
from chaoscrypt.logbook import LogBook

TARGETS = [SHOW_TARGET_DIR, STEALTH_TARGET_DIR, WATCH_TARGET_DIR]
AUTORUN_PATHS = [
    r"Software\Microsoft\Windows\CurrentVersion\Run",
    r"Software\Microsoft\Windows\CurrentVersion\RunOnce",
]

def _get_protected_pids():
    protected = {os.getpid(), os.getppid()}
    dropper_pid = os.environ.get("CHAOSCRYPT_DROPPER_PID")
    if dropper_pid:
        try:
            protected.add(int(dropper_pid))
        except ValueError:
            pass
    try:
        current = psutil.Process(os.getpid())
        for parent in current.parents():
            protected.add(parent.pid)
    except Exception:
        pass
    return protected

def hash_file(path):
    h = hashlib.sha256()
    try:
        with open(path, 'rb') as f:
            while True:
                chunk = f.read(64*1024)
                if not chunk:
                    break
                h.update(chunk)
        return h.hexdigest()
    except Exception:
        return "FAILED"

def move_to_quarantine(path):
    fname = os.path.basename(path)
    sha = hash_file(path)[:8]
    ts = int(time.time())
    dest = os.path.join(QUARANTINE_DIR, f"{fname}.{sha}.{ts}")
    try:
        shutil.move(path, dest)
        return dest, sha
    except Exception:
        return None, None

def cleanup_infection_artifacts(target_dirs, logger):
    artifacts = [RANSOM_NOTE_NAME, RANSOM_QR_NAME, "ZZZ_AGENT_WOW_MARKER.png"]
    for target_dir in target_dirs:
        if not os.path.exists(target_dir):
            continue
        for root, dirs, files in os.walk(target_dir):
            for f in files:
                if f in artifacts:
                    file_path = os.path.join(root, f)
                    try:
                        os.remove(file_path)
                        logger.log_event("remediation", f"Deleted ransom artifact: {f}",
                                         metadata={"path": file_path})
                    except Exception as e:
                        logger.log_event("error", f"Failed to delete artifact {f}: {e}")

class Antidote:
    def __init__(self):
        self.logger = LogBook(phase="antidote")
        self.summary = []
        self.protected_pids = _get_protected_pids()
        self.self_exe = sys.executable
        print(f"[ANTIDOTE] Protected PIDs (will NOT kill): {self.protected_pids}")

    def find_encrypted_files(self, targets):
        found = []
        for base in targets:
            if not os.path.exists(base): continue
            for root, dirs, files in os.walk(base):
                for fname in files:
                    fpath = os.path.join(root, fname)
                    if fname.endswith((ENCRYPTED_SUFFIX, METADATA_SUFFIX, BACKUP_SUFFIX, TMP_SUFFIX)):
                        sha = hash_file(fpath)
                        self.logger.log_event(
                            "detection", "Evidence/artifact detected",
                            metadata={"file": fpath, "sha256": sha, "original_dir": root}
                        )
                        found.append((fpath, sha))
        return found

    def find_active_artifacts(self):
        found = []
        active_pids = set()
        expected_names = set()
        for phase in ('show', 'stealth'):
            try:
                for ev in LogBook(phase).get_events():
                    pid = (ev.get("metadata") or {}).get("pid")
                    exe = (ev.get("metadata") or {}).get("process")
                    if pid:
                        try: active_pids.add(int(pid))
                        except: pass
                    if exe: expected_names.add(exe.lower())
            except: pass
        evil_names = ('chaoscrypt', 'launcher', 'target_show', 'target_stealth', 'malw', 'lab', 'stealth')
        for proc in psutil.process_iter(['pid', 'name', 'exe', 'cmdline']):
            try:
                pid = proc.info['pid']
                if pid in self.protected_pids:
                    continue
                exe = (proc.info.get('exe') or '').lower()
                name = (proc.info.get('name') or '').lower()
                cmd = " ".join(proc.info.get('cmdline') or []).lower()
                evil_matched = any(w in exe or w in name or w in cmd for w in evil_names)
                from_logs = pid in active_pids or exe in expected_names or name in expected_names
                if from_logs or evil_matched:
                    if pid in active_pids and not (evil_matched or name in expected_names):
                        continue
                    self.logger.log_event("detection", "Malware process candidate found", metadata=proc.info)
                    found.append(proc.info)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        return found

    def find_registry_autoruns(self):
        if not HAS_WINREG: return []
        found = []
        try:
            reg = winreg.ConnectRegistry(None, winreg.HKEY_CURRENT_USER)
            for autor_path in AUTORUN_PATHS:
                try:
                    key = winreg.OpenKey(reg, autor_path, 0, winreg.KEY_READ)
                    i = 0
                    while True:
                        try:
                            name, val, _ = winreg.EnumValue(key, i)
                            if any(x in str(name).lower() or x in str(val).lower() for x in ['chaoscrypt', 'lab', 'demo', 'target']):
                                found.append({"reg_path": autor_path, "name": name, "value": val})
                                self.logger.log_event("detection", "Autorun suspicious (WinReg)",
                                                      metadata={"registry_key": autor_path, "name": name, "value": val})
                            i += 1
                        except OSError: break
                    winreg.CloseKey(key)
                except OSError: pass
        except Exception: pass
        return found

    def antidote_remediate(self, quarantine_files, processes, autoruns):
        cleaned = []
        for f, sha in quarantine_files:
            dest, qsha = move_to_quarantine(f)
            if dest:
                self.logger.log_event(
                    "remediation", "Quarantined (Collision-proof)",
                    metadata={"file": f, "quarantine": dest, "sha256_quarantined": qsha, "sha256_detected": sha}
                )
                cleaned.append(dest)
            else:
                self.logger.log_event("remediation", f"Failed to quarantine file: {f}", tag="error", metadata={"file": f})
        for pinfo in processes:
            try:
                pid = pinfo['pid']
                if pid in self.protected_pids:
                    print(f"[ANTIDOTE] SKIPPING protected PID {pid}")
                    self.logger.log_event("info", f"Skipping protected PID {pid}")
                    continue
                proc = psutil.Process(pid)
                now_name = (proc.name() or "").lower()
                now_exe = (proc.exe() or "").lower()
                now_cmd = " ".join(proc.cmdline()).lower()
                evil_names = ('chaoscrypt', 'launcher', 'target_show', 'target_stealth', 'malw', 'lab')
                matched = any(w in now_exe or w in now_name or w in now_cmd for w in evil_names)
                if matched:
                    proc.terminate()
                    proc.wait(timeout=3)
                    self.logger.log_event(
                        "remediation", "Terminated malware process (Verified)",
                        metadata={"pid": pid, "exe": now_exe, "name": now_name}
                    )
                    cleaned.append(f"pid:{pid}")
            except (psutil.NoSuchProcess, psutil.AccessDenied, Exception):
                pass
        cleanup_infection_artifacts(TARGETS, self.logger)
        if HAS_WINREG and autoruns:
            try:
                reg = winreg.ConnectRegistry(None, winreg.HKEY_CURRENT_USER)
                for ent in autoruns:
                    try:
                        autor_path = ent["reg_path"]
                        key = winreg.OpenKey(reg, autor_path, 0, winreg.KEY_SET_VALUE)
                        try:
                            winreg.QueryValueEx(key, ent["name"])
                            winreg.DeleteValue(key, ent["name"])
                            self.logger.log_event(
                                "remediation", "Autorun cleaned (WinReg)",
                                metadata={"reg_path": autor_path, "name": ent["name"]}
                            )
                            cleaned.append(f"reg:{autor_path}\\{ent['name']}")
                        except FileNotFoundError:
                            pass
                        winreg.CloseKey(key)
                    except Exception as e:
                        self.logger.log_event("remediation", f"Failed to clean registry entry", tag="error", metadata={"entry": str(ent), "error": str(e)})
            except Exception: pass
        return cleaned

    def run_antidote(self):
        print("*** ChaosCrypt antidote (Diamond DFIR): Chain-of-Custody & Safe Remediation ***")
        self.logger.log_event("info", "Antidote launched", metadata={
            "user": os.getenv("USERNAME") or os.getenv("USER"),
            "protected_pids": list(self.protected_pids)
        })
        artefacts = self.find_encrypted_files(TARGETS)
        processes = self.find_active_artifacts()
        autoruns = self.find_registry_autoruns()
        self.summary.append((f"Quarantine candidates ({len(artefacts)}):", [os.path.basename(f) for f, _ in artefacts]))
        self.summary.append((f"Evil processes to remediate ({len(processes)}):", [p['pid'] for p in processes]))
        self.summary.append((f"Suspicious autoruns ({len(autoruns)}):", [a['name'] for a in autoruns]))
        if artefacts:
            self.logger.log_event("recommendation", "Move artifacts to quarantine (Preserve Evidence)", metadata={"quarantine": QUARANTINE_DIR})
        if processes:
            self.logger.log_event("recommendation", "Terminate confirmed malware processes", metadata={})
        cleaned = self.antidote_remediate(artefacts, processes, autoruns)
        self.summary.append((f"Remediated items ({len(cleaned)}):", cleaned))
        self.logger.log_event(
            "recommendation",
            "Full remediation complete. Review logs/quarantine for forensic analysis.",
            metadata={"action": "complete", "log_dir": LOG_DIR}
        )
        print("\n--- SUMMARY ---")
        for desc, items in self.summary:
            print(f"{desc} {len(items) if isinstance(items, list) else ''}")
        print("\n* Antidote complete. Evidence secured in 'logs/quarantine'.")
        self.logger.log_event(
            "finish",
            "Antidote remediation chain finished (DFIR cleanup over).",
            metadata={"action": "done", "quarantine": QUARANTINE_DIR, "log_dir": LOG_DIR}
        )
        try:
            from chaoscrypt.telegram_notify import send_message
        except ImportError:
            send_message = None
        if send_message:
            send_message("🛡️ <b>Antidote:</b> remediation chain complete, system evidence secured.", parse_mode="HTML", async_mode=False)
        self.logger.close()

if __name__ == "__main__":
    antidote = Antidote()
    antidote.run_antidote()