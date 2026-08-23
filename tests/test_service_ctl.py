"""Tests for Windows service controller and service class configuration."""

import pytest
from app.constants import SERVICE_NAME, SERVICE_DISPLAY_NAME, SERVICE_DESCRIPTION
from app.service.windows_service import TelegramDownloaderWindowsService
from app.service import service_ctl


def test_service_constants():
    assert SERVICE_NAME == "TelegramDownloader"
    assert SERVICE_DISPLAY_NAME == "Telegram Downloader"
    assert len(SERVICE_DESCRIPTION) > 0


def test_service_class_attributes():
    assert TelegramDownloaderWindowsService._svc_name_ == "TelegramDownloader"
    assert TelegramDownloaderWindowsService._svc_display_name_ == "Telegram Downloader"
    assert TelegramDownloaderWindowsService._svc_description_ == SERVICE_DESCRIPTION


def test_service_status_query():
    status = service_ctl.get_service_status()
    assert isinstance(status, dict)
    assert "installed" in status
    assert "status" in status
