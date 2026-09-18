"""Конфигурация. Всё переопределяется переменными окружения (см. .env.example)."""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def _path(key: str, default: str) -> Path:
    return Path(os.getenv(key, default)).expanduser()


def _int(key: str, default: int) -> int:
    return int(os.getenv(key, str(default)))


def _float(key: str, default: float) -> float:
    return float(os.getenv(key, str(default)))


def _bool(key: str, default: bool) -> bool:
    return os.getenv(key, "1" if default else "0").strip().lower() in ("1", "true", "yes", "on")


# --- пути ---------------------------------------------------------------
DATA_DIR = _path("AUTOEDIT_DATA_DIR", "/var/lib/autoedit")
UPLOAD_DIR = DATA_DIR / "uploads"
OUTPUT_DIR = DATA_DIR / "outputs"
CACHE_DIR = DATA_DIR / "cache"
TMP_DIR = DATA_DIR / "tmp"
DB_PATH = Path(os.getenv("AUTOEDIT_DB", str(DATA_DIR / "autoedit.sqlite3")))
BANNER_PATH = _path("AUTOEDIT_BANNER", str(BASE_DIR / "assets" / "banner.mp4"))
WEB_DIR = _path("AUTOEDIT_WEB_DIR", str(BASE_DIR / "web"))

# --- телеграм / сайт ----------------------------------------------------
BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "https://autoedit.ink").rstrip("/")
SECRET_KEY = os.getenv("SECRET_KEY", "").strip()
# Пустой список = доступ всем. Иначе — только эти telegram id.
ALLOWED_USER_IDS = {
    int(x) for x in os.getenv("ALLOWED_USER_IDS", "").replace(",", " ").split() if x.strip()
}
INIT_DATA_MAX_AGE = _int("INIT_DATA_MAX_AGE", 24 * 3600)

# --- требование рекламодателя ------------------------------------------
# Порог, который проверяет бот рекламодателя.
MIN_COVERAGE = _float("MIN_COVERAGE", 0.25)
# Цель при сквизе: чуть выше порога, чтобы был запас на округления и на то,
# что их бот может считать пиксели немного иначе.
TARGET_COVERAGE = _float("TARGET_COVERAGE", 0.2535)
# Срезать чёрные поля перед замером, чтобы их площадь не попадала в знаменатель.
CROP_BLACK_BARS = _bool("CROP_BLACK_BARS", True)
# Порог альфы, при котором пиксель баннера считается закрывающим кадр.
ALPHA_THRESHOLD = _int("ALPHA_THRESHOLD", 128)

# --- хромакей -----------------------------------------------------------
CHROMAKEY_COLOR = os.getenv("CHROMAKEY_COLOR", "0x00FE00")
CHROMAKEY_SIMILARITY = _float("CHROMAKEY_SIMILARITY", 0.10)
CHROMAKEY_BLEND = _float("CHROMAKEY_BLEND", 0.02)

# --- кодирование --------------------------------------------------------
X264_PRESET = os.getenv("X264_PRESET", "medium")
X264_CRF = _int("X264_CRF", 20)
AUDIO_BITRATE = os.getenv("AUDIO_BITRATE", "128k")
AUDIO_RATE = _int("AUDIO_RATE", 48000)
FPS_MIN, FPS_MAX = 24, 60

# --- лимиты и хранение --------------------------------------------------
MAX_UPLOAD_BYTES = _int("MAX_UPLOAD_BYTES", 2 * 1024 * 1024 * 1024)
MAX_INPUT_DURATION = _float("MAX_INPUT_DURATION", 30 * 60)
LINK_TTL_HOURS = _int("LINK_TTL_HOURS", 48)
RETENTION_HOURS = _int("RETENTION_HOURS", 72)
WORKER_POLL_SECONDS = _float("WORKER_POLL_SECONDS", 2.0)
FFMPEG_TIMEOUT = _int("FFMPEG_TIMEOUT", 3600)
# Файл до этого размера бот умеет отправить прямо в чат, дальше — только ссылка.
TG_SEND_LIMIT_BYTES = _int("TG_SEND_LIMIT_BYTES", 50 * 1024 * 1024)

FFMPEG = os.getenv("FFMPEG_BIN", "ffmpeg")
FFPROBE = os.getenv("FFPROBE_BIN", "ffprobe")


def ensure_dirs() -> None:
    for d in (DATA_DIR, UPLOAD_DIR, OUTPUT_DIR, CACHE_DIR, TMP_DIR):
        d.mkdir(parents=True, exist_ok=True)


def signing_key() -> bytes:
    """Ключ для подписи ссылок на скачивание."""
    if SECRET_KEY:
        return SECRET_KEY.encode()
    if BOT_TOKEN:
        return BOT_TOKEN.encode()
    raise RuntimeError("Нужен SECRET_KEY или BOT_TOKEN в окружении")
