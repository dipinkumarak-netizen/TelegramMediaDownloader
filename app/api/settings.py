"""Application settings and runtime configuration API routes."""

import logging
from typing import Dict, Any

from fastapi import APIRouter, HTTPException, status, Depends

from app.api.deps import get_current_admin
from app.config import settings, save_config
from app.core.storage import validate_storage_path
from app.db.models import SettingsUpdate

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/settings", tags=["Settings"])


@router.get("")
async def get_settings(admin=Depends(get_current_admin)):
    """Returns application configuration settings."""
    return {
        "host": settings.host,
        "port": settings.port,
        "data_dir": str(settings.data_dir),
        "download_dir": settings.download_dir,
        "log_level": settings.log_level,
        "max_concurrent_downloads": settings.max_concurrent_downloads,
        "free_space_threshold_mb": settings.free_space_threshold_mb,
        "max_retries": settings.max_retries,
        "retry_delay_seconds": settings.retry_delay_seconds,
        "telegram_configured": bool(settings.telegram_api_id and settings.telegram_api_hash),
        "telegram_phone": settings.telegram_phone,
        "jellyfin_url": settings.jellyfin_url,
        "jellyfin_configured": bool(settings.jellyfin_url and settings.jellyfin_api_key),
        "jellyfin_auto_refresh": settings.jellyfin_auto_refresh,
    }


@router.put("")
async def update_settings(payload: SettingsUpdate, admin=Depends(get_current_admin)):
    """Updates runtime application settings."""
    if payload.download_dir is not None:
        valid, msg = validate_storage_path(payload.download_dir)
        if not valid:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=msg)
        settings.download_dir = payload.download_dir.strip()

    if payload.host is not None:
        settings.host = payload.host.strip()
    if payload.port is not None:
        if not (1 <= payload.port <= 65535):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Port must be between 1 and 65535.")
        settings.port = payload.port
    if payload.log_level is not None:
        settings.log_level = payload.log_level.upper()
    if payload.max_concurrent_downloads is not None:
        settings.max_concurrent_downloads = max(1, min(10, payload.max_concurrent_downloads))
    if payload.free_space_threshold_mb is not None:
        settings.free_space_threshold_mb = max(100, payload.free_space_threshold_mb)
    if payload.max_retries is not None:
        settings.max_retries = max(0, min(10, payload.max_retries))
    if payload.retry_delay_seconds is not None:
        settings.retry_delay_seconds = max(1, min(300, payload.retry_delay_seconds))

    if payload.jellyfin_url is not None:
        settings.jellyfin_url = payload.jellyfin_url.strip() if payload.jellyfin_url else None
    if payload.jellyfin_api_key is not None:
        settings.jellyfin_api_key = payload.jellyfin_api_key.strip() if payload.jellyfin_api_key else None
    if payload.jellyfin_auto_refresh is not None:
        settings.jellyfin_auto_refresh = payload.jellyfin_auto_refresh

    save_config(settings)
    logger.info("Application settings updated successfully.")
    return {"status": "success", "message": "Settings saved successfully."}
