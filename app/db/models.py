"""Data schemas, database models, and API request/response contracts."""

from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, field_validator

from app.constants import (
    DownloadStatus,
    SourceType,
    TELEGRAM_MAX_SIGNED_32BIT_INT,
    TELEGRAM_MIN_SIGNED_32BIT_INT,
)


# ==========================================
# Auth Models
# ==========================================

class SetupStatusResponse(BaseModel):
    is_setup_completed: bool
    version: str
    data_dir: str
    download_dir: Optional[str]
    is_telegram_configured: bool
    is_telegram_authenticated: bool


class SetupWizardRequest(BaseModel):
    username: str = Field(min_length=3, max_length=50)
    password: str = Field(min_length=6, max_length=100)
    download_dir: str
    telegram_api_id: Optional[int] = None
    telegram_api_hash: Optional[str] = None
    telegram_phone: Optional[str] = None
    jellyfin_url: Optional[str] = None
    jellyfin_api_key: Optional[str] = None
    jellyfin_auto_refresh: bool = False

    @field_validator("telegram_api_id")
    @classmethod
    def check_api_id(cls, v: Optional[int]) -> Optional[int]:
        if v is None:
            return None
        if not (TELEGRAM_MIN_SIGNED_32BIT_INT <= v <= TELEGRAM_MAX_SIGNED_32BIT_INT):
            raise ValueError(
                f"Telegram API ID must be between {TELEGRAM_MIN_SIGNED_32BIT_INT} and {TELEGRAM_MAX_SIGNED_32BIT_INT}."
            )
        return v


class LoginRequest(BaseModel):
    username: str
    password: str


class AdminUser(BaseModel):
    id: int
    username: str
    created_at: str
    last_login: Optional[str] = None


class UserResponse(BaseModel):
    username: str
    is_authenticated: bool


# ==========================================
# Telegram Models
# ==========================================

class TelegramConfigPayload(BaseModel):
    api_id: int
    api_hash: str
    phone: str

    @field_validator("api_id")
    @classmethod
    def check_api_id(cls, v: int) -> int:
        if not (TELEGRAM_MIN_SIGNED_32BIT_INT <= v <= TELEGRAM_MAX_SIGNED_32BIT_INT):
            raise ValueError(
                f"API ID must be between {TELEGRAM_MIN_SIGNED_32BIT_INT} and {TELEGRAM_MAX_SIGNED_32BIT_INT}."
            )
        return v


class TelegramCodePayload(BaseModel):
    phone_code: str


class TelegramPasswordPayload(BaseModel):
    password: str


class TelegramStatusResponse(BaseModel):
    status: str  # UNCONFIGURED, DISCONNECTED, WAITING_CODE, WAITING_PASSWORD, CONNECTED, ERROR
    is_connected: bool
    is_authorized: bool
    phone: Optional[str] = None
    user_id: Optional[int] = None
    first_name: Optional[str] = None
    username: Optional[str] = None
    error_message: Optional[str] = None


# ==========================================
# Telegram Source Models
# ==========================================

class SourceCreate(BaseModel):
    telegram_id: str  # e.g. "@channel", "https://t.me/...", "-100123456789"
    title: Optional[str] = None
    source_type: SourceType = SourceType.CHANNEL
    is_enabled: bool = True
    download_videos: bool = True
    download_documents: bool = True
    download_audio: bool = True
    download_images: bool = False
    download_archives: bool = True
    min_size_bytes: Optional[int] = 0
    max_size_bytes: Optional[int] = 0  # 0 means unlimited
    custom_subfolder: Optional[str] = None


class SourceUpdate(BaseModel):
    title: Optional[str] = None
    is_enabled: Optional[bool] = None
    download_videos: Optional[bool] = None
    download_documents: Optional[bool] = None
    download_audio: Optional[bool] = None
    download_images: Optional[bool] = None
    download_archives: Optional[bool] = None
    min_size_bytes: Optional[int] = None
    max_size_bytes: Optional[int] = None
    custom_subfolder: Optional[str] = None


class SourceResponse(BaseModel):
    id: int
    telegram_id: str
    title: str
    username: Optional[str] = None
    source_type: str
    is_enabled: bool
    download_videos: bool
    download_documents: bool
    download_audio: bool
    download_images: bool
    download_archives: bool
    min_size_bytes: int
    max_size_bytes: int
    custom_subfolder: Optional[str] = None
    created_at: str
    updated_at: str


# ==========================================
# Download Models
# ==========================================

class DownloadItem(BaseModel):
    id: int
    telegram_chat_id: str
    telegram_message_id: int
    source_title: Optional[str] = None
    filename: str
    sanitized_filename: str
    destination_path: str
    file_size: int
    file_size_formatted: str
    mime_type: Optional[str] = None
    status: DownloadStatus
    progress_percent: float
    downloaded_bytes: int
    downloaded_formatted: str
    speed_bytes_per_sec: float
    speed_formatted: str
    eta_seconds: Optional[int] = None
    retry_count: int
    max_retries: int
    error_message: Optional[str] = None
    created_at: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None


class DownloadsStats(BaseModel):
    total: int
    queued: int
    downloading: int
    completed: int
    failed: int
    cancelled: int
    retrying: int
    total_downloaded_bytes: int
    total_downloaded_formatted: str
    current_speed_bytes_per_sec: float
    current_speed_formatted: str


# ==========================================
# Jellyfin Models
# ==========================================

class JellyfinConfig(BaseModel):
    url: Optional[str] = None
    api_key: Optional[str] = None
    auto_refresh: bool = False


class JellyfinTestResponse(BaseModel):
    success: bool
    message: str
    server_name: Optional[str] = None
    version: Optional[str] = None


# ==========================================
# Settings & System Models
# ==========================================

class StorageSelection(BaseModel):
    download_dir: str


class SettingsUpdate(BaseModel):
    host: Optional[str] = None
    port: Optional[int] = None
    download_dir: Optional[str] = None
    log_level: Optional[str] = None
    max_concurrent_downloads: Optional[int] = None
    free_space_threshold_mb: Optional[int] = None
    max_retries: Optional[int] = None
    retry_delay_seconds: Optional[int] = None
    jellyfin_url: Optional[str] = None
    jellyfin_api_key: Optional[str] = None
    jellyfin_auto_refresh: Optional[bool] = None


class SystemStatusResponse(BaseModel):
    service_status: str
    uptime_seconds: int
    uptime_formatted: str
    cpu_percent: float
    ram_percent: float
    ram_used_formatted: str
    ram_total_formatted: str
    app_version: str
    python_version: str
    os_name: str
