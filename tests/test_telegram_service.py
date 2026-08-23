"""Tests for Telegram service, MTProto API ID validation, and source filtering."""

import pytest
from app.services.telegram_service import telegram_service
from app.services.source_manager import source_manager


def test_telegram_api_id_validation():
    # Valid IDs
    assert telegram_service.validate_api_id(12345678) == 12345678
    assert telegram_service.validate_api_id("28941234") == 28941234
    assert telegram_service.validate_api_id(2147483647) == 2147483647

    # Out-of-range IDs (> 32-bit signed int max, like 5544720785)
    with pytest.raises(ValueError) as exc:
        telegram_service.validate_api_id(5544720785)
    assert "32-bit signed integer" in str(exc.value)

    # Non-numeric strings
    with pytest.raises(ValueError):
        telegram_service.validate_api_id("not_a_number")


def test_telegram_initial_status():
    status = telegram_service.get_status()
    assert "status" in status
    assert "is_connected" in status
    assert "is_authorized" in status
