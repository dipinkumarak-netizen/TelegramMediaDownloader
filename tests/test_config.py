"""Tests for configuration system, hierarchy, and 32-bit Telegram API ID bounds validation."""

import pytest
from pydantic import ValidationError
from app.config import AppSettings
from app.constants import TELEGRAM_MAX_SIGNED_32BIT_INT, TELEGRAM_MIN_SIGNED_32BIT_INT


def test_default_settings():
    settings = AppSettings()
    assert settings.host == "0.0.0.0"
    assert settings.port == 8787
    assert settings.max_concurrent_downloads == 2
    assert settings.free_space_threshold_mb == 1024


def test_telegram_api_id_valid():
    # Valid 32-bit integers
    s1 = AppSettings(telegram_api_id=28941234)
    assert s1.telegram_api_id == 28941234

    s2 = AppSettings(telegram_api_id=TELEGRAM_MAX_SIGNED_32BIT_INT)
    assert s2.telegram_api_id == 2147483647

    s3 = AppSettings(telegram_api_id=TELEGRAM_MIN_SIGNED_32BIT_INT)
    assert s3.telegram_api_id == 1


def test_telegram_api_id_invalid_overflow():
    # Number > 2147483647 (e.g. Bot ID or user ID like 5544720785)
    with pytest.raises(ValidationError) as exc:
        AppSettings(telegram_api_id=5544720785)
    assert "Invalid Telegram API ID" in str(exc.value)


def test_telegram_api_id_invalid_negative():
    with pytest.raises(ValidationError):
        AppSettings(telegram_api_id=-5)
