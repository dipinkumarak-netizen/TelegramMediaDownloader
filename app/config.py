"""Centralized configuration system with 4-tier hierarchy:
1. Environment Variables
2. Config File (config.json)
3. Database Settings
4. Safe Defaults
"""

import json
import os
import secrets
from pathlib import Path
from typing import Optional, Dict, Any
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.constants import (
    APP_DATA_DIR,
    CONFIG_DIR,
    CONFIG_FILE_PATH,
    DATABASE_DIR,
    LOGS_DIR,
    SESSION_DIR,
    TEMP_DIR,
    DEFAULT_HOST,
    DEFAULT_PORT,
    DEFAULT_MAX_CONCURRENT_DOWNLOADS,
    DEFAULT_FREE_SPACE_THRESHOLD_MB,
    DEFAULT_MAX_RETRIES,
    DEFAULT_RETRY_DELAY_SECONDS,
    DEFAULT_DOWNLOAD_WORKERS,
    TELEGRAM_MAX_SIGNED_32BIT_INT,
    TELEGRAM_MIN_SIGNED_32BIT_INT,
)


class AppSettings(BaseSettings):
    """Application configuration schema."""
    model_config = SettingsConfigDict(
        env_prefix="TELEGRAM_DOWNLOADER_",
        env_file=".env",
        extra="ignore"
    )

    # Core Paths
    data_dir: Path = Field(default=APP_DATA_DIR)
    download_dir: Optional[str] = Field(default=None)

    # Server Settings
    host: str = Field(default=DEFAULT_HOST)
    port: int = Field(default=DEFAULT_PORT)
    log_level: str = Field(default="INFO")
    secret_key: str = Field(default_factory=lambda: secrets.token_hex(32))
    is_production: bool = Field(default=True)

    # Download Engine Settings
    max_concurrent_downloads: int = Field(default=DEFAULT_MAX_CONCURRENT_DOWNLOADS)
    download_workers: int = Field(default=DEFAULT_DOWNLOAD_WORKERS)
    free_space_threshold_mb: int = Field(default=DEFAULT_FREE_SPACE_THRESHOLD_MB)
    max_retries: int = Field(default=DEFAULT_MAX_RETRIES)
    retry_delay_seconds: int = Field(default=DEFAULT_RETRY_DELAY_SECONDS)

    # Telegram Credentials
    telegram_api_id: Optional[int] = Field(default=None)
    telegram_api_hash: Optional[str] = Field(default=None)
    telegram_phone: Optional[str] = Field(default=None)

    # Jellyfin Integration
    jellyfin_url: Optional[str] = Field(default=None)
    jellyfin_api_key: Optional[str] = Field(default=None)
    jellyfin_auto_refresh: bool = Field(default=False)

    @field_validator("telegram_api_id")
    @classmethod
    def validate_telegram_api_id(cls, v: Optional[int]) -> Optional[int]:
        if v is None:
            return None
        if not (TELEGRAM_MIN_SIGNED_32BIT_INT <= v <= TELEGRAM_MAX_SIGNED_32BIT_INT):
            raise ValueError(
                f"Invalid Telegram API ID '{v}'. Telegram MTProto API IDs must be 32-bit signed integers "
                f"between {TELEGRAM_MIN_SIGNED_32BIT_INT} and {TELEGRAM_MAX_SIGNED_32BIT_INT}. "
                f"Make sure you entered your App API ID from https://my.telegram.org/apps (NOT a bot token or user ID)."
            )
        return v

    def ensure_directories(self) -> None:
        """Ensures all internal application directories exist."""
        self.data_dir.mkdir(parents=True, exist_ok=True)
        (self.data_dir / "config").mkdir(parents=True, exist_ok=True)
        (self.data_dir / "database").mkdir(parents=True, exist_ok=True)
        (self.data_dir / "logs").mkdir(parents=True, exist_ok=True)
        (self.data_dir / "session").mkdir(parents=True, exist_ok=True)
        (self.data_dir / "temp").mkdir(parents=True, exist_ok=True)


def load_config() -> AppSettings:
    """Loads configuration from config.json merged with environment variables."""
    # Ensure config dir exists
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    
    file_data: Dict[str, Any] = {}
    if CONFIG_FILE_PATH.exists():
        try:
            with open(CONFIG_FILE_PATH, "r", encoding="utf-8") as f:
                file_data = json.load(f)
        except Exception:
            file_data = {}

    settings = AppSettings(**file_data)
    settings.ensure_directories()
    
    # If secret_key was newly generated, save it back to file
    if "secret_key" not in file_data:
        save_config(settings)

    return settings


def save_config(settings: AppSettings) -> None:
    """Saves updated settings to config.json."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    data = settings.model_dump(mode="json")
    
    # Convert Path objects to string for JSON serialization
    if "data_dir" in data:
        data["data_dir"] = str(data["data_dir"])
        
    with open(CONFIG_FILE_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


# Global settings instance
settings = load_config()
