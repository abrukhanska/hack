import os

try:
    from dotenv import load_dotenv
    dotenv_path = os.path.join(os.path.dirname(__file__), ".env")
    if os.path.exists(dotenv_path):
        load_dotenv(dotenv_path)
except ImportError:
    pass

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
LOG_DIR = os.path.join(ROOT_DIR, "logs")
QUARANTINE_DIR = os.path.join(LOG_DIR, "quarantine")
SHOW_TARGET_DIR = os.path.join(ROOT_DIR, "Target_Show")
STEALTH_TARGET_DIR = os.path.join(ROOT_DIR, "Target_Stealth")
ASSETS_DIR = os.path.join(ROOT_DIR, "assets")
WATCH_TARGET_DIR = os.path.join(ROOT_DIR, "Target_Watched")

for path in [LOG_DIR, QUARANTINE_DIR, SHOW_TARGET_DIR, STEALTH_TARGET_DIR, WATCH_TARGET_DIR]:
    os.makedirs(path, exist_ok=True)

ENCRYPTED_SUFFIX   = ".cclab"
METADATA_SUFFIX    = ".meta"
BACKUP_SUFFIX      = ".bak"
TMP_SUFFIX         = ".tmp"
CHUNK_SIZE         = 64 * 1024
LOCK_TIMEOUT       = 60

LOGFILES = {
    'show':         os.path.join(LOG_DIR, 'master_show.jsonl'),
    'stealth':      os.path.join(LOG_DIR, 'master_stealth.jsonl'),
    'antidote':     os.path.join(LOG_DIR, 'master_antidote.jsonl'),
    'recovery':     os.path.join(LOG_DIR, 'master_recovery.jsonl'),
    'system_hooks': os.path.join(LOG_DIR, 'master_system_hooks.jsonl'),
    'dropper':      os.path.join(LOG_DIR, 'master_dropper.jsonl'),
    'network':      os.path.join(LOG_DIR, 'master_network.jsonl'),
    'agent':        os.path.join(LOG_DIR, 'master_agent.jsonl'),
    'c2':           os.path.join(LOG_DIR, 'master_c2.jsonl'),
    'chaos':        os.path.join(LOG_DIR, 'master_chaos.jsonl'),
}

PARSE_ERROR_LOG = os.path.join(LOG_DIR, 'parsing_errors.log')
TXT_LOGS = {
    'show':         os.path.join(LOG_DIR, 'show_case.log'),
    'stealth':      os.path.join(LOG_DIR, 'stealth_case.log'),
    'antidote':     os.path.join(LOG_DIR, 'antidote.log'),
    'recovery':     os.path.join(LOG_DIR, 'shared_recovery.log'),
    'system_hooks': os.path.join(LOG_DIR, 'system_hooks.log'),
    'dropper':      os.path.join(LOG_DIR, 'dropper_engine.log'),
    'network':      os.path.join(LOG_DIR, 'network_monitor.log'),
    'agent':        os.path.join(LOG_DIR, 'agent_file.log'),
    'c2':           os.path.join(LOG_DIR, 'c2_commander.log'),
    'chaos':        os.path.join(LOG_DIR, 'chaos_effects.log'),
}

ROTATE_MAX_BYTES = 50 * 1024 * 1024

TELEGRAM_TOKEN    = os.getenv("CHAOSCRYPT_TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID  = os.getenv("CHAOSCRYPT_TELEGRAM_CHAT_ID", "")

TELEGRAM_AUTO_NOTIFY = bool(TELEGRAM_TOKEN) and bool(TELEGRAM_CHAT_ID)

DEFAULT_ENCRYPT_DELAY_SEC = 5.0
DEFAULT_STEALTH_LAG_SEC   = 7.0
SAFE_MODE                = True
DEBUG_LEVEL              = "INFO"
DEMO_PHASES         = ["show", "stealth", "antidote", "recovery"]
TEACHING_WOW_DEMO   = True
DFIR_MODE           = True

RANSOM_NOTE_NAME = "!!!_READ_ME_NOW_!!!.txt"
RANSOM_QR_NAME   = "!!!_DECRYPT_FILES_PAYMENT_QR.png"

IMG_LOGO_REPORT  = "chaos_logo_whitebg.jpg"
IMG_LOGO_SYSTEM  = "chaos_logo_transparent.png"
IMG_SUCCESS      = "chaoscrypt_success.jpg"
IMG_ICO_NAME     = "chaos_icon.ico"

ALL_PHASES = (
    'system_hooks', 'dropper', 'network', 'c2', 'agent', 'chaos', 'show', 'stealth', 'antidote', 'recovery'
)

__all__ = [
    "ROOT_DIR", "LOG_DIR", "QUARANTINE_DIR",
    "SHOW_TARGET_DIR", "STEALTH_TARGET_DIR", "ASSETS_DIR", "WATCH_TARGET_DIR",
    "ENCRYPTED_SUFFIX", "METADATA_SUFFIX", "BACKUP_SUFFIX", "TMP_SUFFIX",
    "CHUNK_SIZE", "LOCK_TIMEOUT",
    "LOGFILES", "TXT_LOGS", "ROTATE_MAX_BYTES", "PARSE_ERROR_LOG",
    "TELEGRAM_TOKEN", "TELEGRAM_CHAT_ID", "TELEGRAM_AUTO_NOTIFY",
    "DEFAULT_ENCRYPT_DELAY_SEC", "DEFAULT_STEALTH_LAG_SEC",
    "SAFE_MODE", "DEBUG_LEVEL", "DEMO_PHASES", "TEACHING_WOW_DEMO", "DFIR_MODE",
    "RANSOM_NOTE_NAME", "RANSOM_QR_NAME",
    "IMG_SUCCESS", "IMG_LOGO_REPORT", "IMG_LOGO_SYSTEM", "IMG_ICO_NAME",
    "ALL_PHASES",
    "WATCH_TARGET_DIR"
]