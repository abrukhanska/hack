import os
import threading
import requests
from chaoscrypt.settings import TELEGRAM_TOKEN, TELEGRAM_CHAT_ID

def _tg_api_url(method):
    return f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/{method}"

def send_message(text, parse_mode=None, async_mode=False):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("[TG] ERROR: Missing TG token/chat_id")
        return 0, "Missing TG token/chat_id"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text
    }
    if parse_mode:
        payload["parse_mode"] = parse_mode
    def _send():
        try:
            resp = requests.post(_tg_api_url("sendMessage"), json=payload, timeout=10)
            if resp.status_code != 200:
                print("[TG] send_message failed:", resp.text)
            return resp.status_code, resp.text
        except Exception as e:
            print("[TG] send_message CRIT fail:", e)
            return 0, f"TG error: {e}"

    if async_mode:
        t = threading.Thread(target=_send, daemon=True)
        t.start()
        return 202, "Sent async (threaded)"
    else:
        return _send()

def send_document(file_path, caption=None, async_mode=False):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("[TG] ERROR: Missing TG token/chat_id")
        return 0, "Missing TG token/chat_id"
    if not os.path.isfile(file_path):
        print("[TG] ERROR: File not found:", file_path)
        return 0, "File not found: " + str(file_path)
    url = _tg_api_url("sendDocument")
    def _send():
        files = {'document': open(file_path, 'rb')}
        data = {"chat_id": TELEGRAM_CHAT_ID}
        if caption:
            data['caption'] = caption
        try:
            resp = requests.post(url, data=data, files=files, timeout=15)
            if resp.status_code != 200:
                print("[TG] send_document failed:", resp.text)
            return resp.status_code, resp.text
        except Exception as e:
            print("[TG] send_document CRIT fail:", e)
            return 0, f"TG error: {e}"
        finally:
            files['document'].close()
    if async_mode:
        t = threading.Thread(target=_send, daemon=True)
        t.start()
        return 202, "Sent async (threaded)"
    else:
        return _send()

def send_photo(file_path, caption=None, parse_mode=None, async_mode=False):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("[TG] ERROR: Missing TG token/chat_id")
        return 0, "Missing TG token/chat_id"
    if not os.path.isfile(file_path):
        print("[TG] ERROR: File not found (photo):", file_path)
        return 0, "File not found"
    url = _tg_api_url("sendPhoto")
    def _send():
        files = {'photo': open(file_path, 'rb')}
        data = {"chat_id": TELEGRAM_CHAT_ID}
        if caption:
            data['caption'] = caption
        if parse_mode:
            data['parse_mode'] = parse_mode
        try:
            resp = requests.post(url, data=data, files=files, timeout=15)
            if resp.status_code != 200:
                print("[TG] send_photo failed:", resp.text)
            return resp.status_code, resp.text
        except Exception as e:
            print("[TG] send_photo CRIT fail:", e)
            return 0, f"TG error: {e}"
        finally:
            files["photo"].close()
    if async_mode:
        t = threading.Thread(target=_send, daemon=True)
        t.start()
        return 202, "Sent async (threaded)"
    else:
        return _send()

def send_alert(text, emoji="⚠️"):
    msg = f"{emoji} {text}"
    return send_message(msg, async_mode=True)

def tg_notify_wow(msg, phase="demo"):
    tag = {"show": "🟢", "stealth": "🔵", "antidote": "🔴", "demo": "✨", "timeline": "📊", "recovery": "✅"}.get(phase, "💡")
    return send_message(f"{tag} {phase.upper()}:\n{msg}", async_mode=True)

def is_ready():
    return bool(TELEGRAM_TOKEN) and bool(TELEGRAM_CHAT_ID)