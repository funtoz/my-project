import os
from dotenv import load_dotenv

load_dotenv()

# Telegram
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# Пути
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMP_DIR = os.path.join(BASE_DIR, "data", "temp")
PROCESSED_DIR = os.path.join(BASE_DIR, "data", "processed")

# Ограничения
MAX_VIDEO_DURATION = int(os.getenv("MAX_VIDEO_DURATION", 180))  # 3 минуты
MAX_FILE_SIZE_MB = int(os.getenv("MAX_FILE_SIZE_MB", 500))

# FFmpeg
FFMPEG_THREADS = int(os.getenv("FFMPEG_THREADS", 4))
VIDEO_QUALITY = int(os.getenv("VIDEO_QUALITY", 23))  # CRF значение (меньше = лучше качество)

# Создаём директории если их нет
os.makedirs(TEMP_DIR, exist_ok=True)
os.makedirs(PROCESSED_DIR, exist_ok=True)
