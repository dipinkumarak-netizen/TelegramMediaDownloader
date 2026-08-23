"""Tests for Jellyfin integration and connection handler."""

import pytest
from app.services.jellyfin_service import jellyfin_service


@pytest.mark.asyncio
async def test_jellyfin_unconfigured():
    # Empty URL / Key should return clean failure dict, never raise
    res1 = await jellyfin_service.test_connection(None, None)
    assert res1["success"] is False
    assert "not configured" in res1["message"].lower()

    res2 = await jellyfin_service.test_connection("http://invalid.local:8096", "")
    assert res2["success"] is False


@pytest.mark.asyncio
async def test_jellyfin_trigger_unconfigured():
    # Triggering refresh when not configured should safely return False
    res = await jellyfin_service.trigger_library_refresh("", "")
    assert res is False
