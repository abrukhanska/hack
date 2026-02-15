import os
import sys
import socket
import time
import threading
import datetime
import shutil

# WOW-import-fix: DRY з settings
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.append(parent_dir)

from chaoscrypt.settings import (
    LOG_DIR, ASSETS_DIR, LOGFILES, TXT_LOGS, IMG_SUCCESS, IMG_LOGO_SYSTEM
)
from chaoscrypt.logbook import LogBook

try:
    from chaoscrypt.telegram_notify import send_message, send_photo
except ImportError:
    send_message = None
    send_photo = None

# === Фазова змінна (for DFIR/logbook)
PHASE = "network"

# Додати phase до settings.py (LOGFILES та TXT_LOGS)
NETWORK_LOG_PATH = LOGFILES.get(PHASE, os.path.join(LOG_DIR, "master_network.jsonl"))
NETWORK_TXT_LOG = TXT_LOGS.get(PHASE, os.path.join(LOG_DIR, "network_monitor.log"))

SERVER_PORT = 5654
SERVER_TIMEOUT_SEC = 10
PCAP_FOLDER = os.path.join(LOG_DIR, "net_pcap")
os.makedirs(PCAP_FOLDER, exist_ok=True)

class SimpleC2Server(threading.Thread):
    """
    Симпл мережевий "C2" сервер на локалці для DEMO (teach/CTF осередок).
    """
    def __init__(self, port, logbook):
        super().__init__(daemon=True)
        self.port = port
        self.logbook = logbook
        self.running = False

    def run(self):
        self.running = True
        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv.settimeout(SERVER_TIMEOUT_SEC)
        try:
            srv.bind(("", self.port))
            srv.listen(5)
            self.logbook.log_event("network", f"C2 Server started on port {self.port}")
            while self.running:
                try:
                    client, addr = srv.accept()
                    data = client.recv(4096)
                    msg = data.decode(errors='ignore')
                    self.logbook.log_event("network", f"Received network payload", metadata={"addr": addr, "bytes": len(data), "content": msg[:256]})
                    client.sendall(b"ACK\n")
                    client.close()
                except socket.timeout:
                    continue
                except Exception as e:
                    self.logbook.log_event("error", f"C2 handler error: {e}")
        except Exception as e:
            self.logbook.log_event("error", f"C2 Server start FAIL: {e}")
        finally:
            srv.close()
            self.logbook.log_event("network", "C2 Server stopped")

    def stop(self):
        self.running = False

def save_pcap_sim(data_bytes, filename="netcap_demo.pcap"):
    """
    Симулює "PCAP" — зберігає raw трафік для teach/BlueTeam з аналізу.
    """
    cap_path = os.path.join(PCAP_FOLDER, filename)
    with open(cap_path, "ab") as f:
        f.write(data_bytes)
    return cap_path

def wow_exfil_sim(logbook, exfil_path):
    """
    Wow: Симуляція мережевого витоку даних та TG-репорт.
    """
    try:
        with open(exfil_path, "rb") as f:
            exfil_bytes = f.read()
        cap_path = save_pcap_sim(exfil_bytes, filename=f"exfil_{int(time.time())}.pcap")
        logbook.log_event(
            "exfiltration", f"Simulated exfil: {os.path.basename(exfil_path)} ({len(exfil_bytes)} bytes)",
            metadata={"pcap_file": cap_path}
        )
        if send_photo and os.path.exists(os.path.join(ASSETS_DIR, IMG_SUCCESS)):
            send_photo(os.path.join(ASSETS_DIR, IMG_SUCCESS),
                caption=f"🚦 WOW: Exfil of {os.path.basename(exfil_path)} complete!\n(PCAP simulated, see logs.)",
                async_mode=False
            )
    except Exception as e:
        logbook.log_event("error", f"Exfil simulation error: {e}")

def run_network_monitor():
    logbook = LogBook(phase=PHASE)
    logbook.log_event("info", "Network Monitor started")
    srv = SimpleC2Server(port=SERVER_PORT, logbook=logbook)
    srv.start()
    # WOW: демо-файл для витоку (можна підкинути .txt/.png для teach)
    demo_exfil_path = os.path.join(ASSETS_DIR, "demo_exfil.txt")
    if os.path.exists(demo_exfil_path):
        wow_exfil_sim(logbook, demo_exfil_path)
    else:
        # Просто демо exfil через зображення-логотип
        logo_path = os.path.join(ASSETS_DIR, IMG_LOGO_SYSTEM)
        if os.path.exists(logo_path):
            wow_exfil_sim(logbook, logo_path)
    try:
        if send_message:
            send_message(f"🌐 [Network] C2 DEMO server active on port {SERVER_PORT}", async_mode=False)
        # Працює у teach-режимі, чекає на вхідні demo-трафіки ~10сек після запуску
        time.sleep(SERVER_TIMEOUT_SEC)
    finally:
        srv.stop()
        time.sleep(1)
    logbook.log_event("info", "Network Monitor finished")
    logbook.close()
    if send_message:
        send_message("🌐 Network monitor phase complete!", async_mode=False)

if __name__ == "__main__":
    run_network_monitor()