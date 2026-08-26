"""Application constants and default paths for Windows 11 environment."""

import os
from enum import Enum
from pathlib import Path


class DownloadStatus(str, Enum):
    QUEUED = "QUEUED"
    DOWNLOADING = "DOWNLOADING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    RETRYING = "RETRYING"


class TelegramAuthState(str, Enum):
    UNCONFIGURED = "UNCONFIGURED"
    DISCONNECTED = "DISCONNECTED"
    WAITING_CODE = "WAITING_CODE"
    WAITING_PASSWORD = "WAITING_PASSWORD"
    CONNECTED = "CONNECTED"
    ERROR = "ERROR"


class SourceType(str, Enum):
    CHANNEL = "CHANNEL"
    SUPERGROUP = "SUPERGROUP"
    GROUP = "GROUP"
    SAVED_MESSAGES = "SAVED_MESSAGES"


# Base application directory
DEFAULT_APP_DATA_ENV = "TELEGRAM_DOWNLOADER_DATA_DIR"


def get_default_data_dir() -> Path:
    """Returns the default AppData directory for Windows or custom path.
    
    Default: %ProgramData%\\TelegramDownloader (e.g. C:\\ProgramData\\TelegramDownloader)
    Fallback: ./data if ProgramData is unavailable or overridden.
    """
    if custom_env := os.getenv(DEFAULT_APP_DATA_ENV):
        return Path(custom_env).resolve()
    
    program_data = os.getenv("ProgramData") or os.getenv("ALLUSERSPROFILE")
    if program_data:
        return (Path(program_data) / "TelegramDownloader").resolve()
    
    # Fallback to local data dir in current directory
    return (Path(__file__).parent.parent / "data").resolve()


APP_DATA_DIR = get_default_data_dir()
CONFIG_DIR = APP_DATA_DIR / "config"
DATABASE_DIR = APP_DATA_DIR / "database"
LOGS_DIR = APP_DATA_DIR / "logs"
SESSION_DIR = APP_DATA_DIR / "session"
TEMP_DIR = APP_DATA_DIR / "temp"

CONFIG_FILE_PATH = CONFIG_DIR / "config.json"
DATABASE_FILE_PATH = DATABASE_DIR / "telegram_downloader.db"
LOG_FILE_PATH = LOGS_DIR / "app.log"
SESSION_FILE_PATH = SESSION_DIR / "telegram.session"

# Defaults
DEFAULT_HOST = "0.0.0.0"
DEFAULT_PORT = 8787
DEFAULT_MAX_CONCURRENT_DOWNLOADS = 2
DEFAULT_FREE_SPACE_THRESHOLD_MB = 1024  # 1 GB
DEFAULT_MAX_RETRIES = 3
DEFAULT_RETRY_DELAY_SECONDS = 15
DEFAULT_DOWNLOAD_CHUNK_SIZE = 1024 * 1024  # 1 MB
DEFAULT_DOWNLOAD_WORKERS = 4  # Concurrent parallel chunk streams per download

# Telegram Protocol Constants
TELEGRAM_MAX_SIGNED_32BIT_INT = 2147483647
TELEGRAM_MIN_SIGNED_32BIT_INT = 1

# Windows Service Constants
SERVICE_NAME = "TelegramDownloader"
SERVICE_DISPLAY_NAME = "Telegram Downloader"
SERVICE_DESCRIPTION = "24/7 background Telegram media downloader and monitor service."
