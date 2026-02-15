from chaoscrypt.settings import TELEGRAM_TOKEN, TELEGRAM_CHAT_ID
from chaoscrypt.telegram_notify import send_message

def check_telegram():
    print("TELEGRAM_TOKEN:", "Set" if TELEGRAM_TOKEN else "Missing")
    print("TELEGRAM_CHAT_ID:", TELEGRAM_CHAT_ID)
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("❌ Token or Chat_ID not set. Check your .env/config!")
        return
    code = "test-" + str(abs(hash(TELEGRAM_CHAT_ID)) % 99999)
    status, resp = send_message(f"ChaosCrypt TG Test OK: {code}")
    if status == 200:
        print("✅ TG notification sent successfully! (code:", code, ")")
    else:
        print("❌ TG notification failed! Status:", status)
        print("TG API response:", resp)

if __name__ == "__main__":
    check_telegram()