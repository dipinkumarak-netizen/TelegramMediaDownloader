"""Jellyfin integration and media library sync API routes."""

import logging
from typing import Dict, Any

from fastapi import APIRouter, HTTPException, status, Depends

from app.api.deps import get_current_admin
from app.config import settings, save_config
from app.db.models import JellyfinConfig, JellyfinTestResponse
from app.services.jellyfin_service import jellyfin_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/jellyfin", tags=["Jellyfin"])


@router.get("/config", response_model=JellyfinConfig)
async def get_jellyfin_config(admin=Depends(get_current_admin)):
    """Returns current Jellyfin integration settings."""
    return JellyfinConfig(
        url=settings.jellyfin_url,
        api_key=settings.jellyfin_api_key,
        auto_refresh=settings.jellyfin_auto_refresh,
    )


@router.put("/config", response_model=JellyfinConfig)
async def update_jellyfin_config(payload: JellyfinConfig, admin=Depends(get_current_admin)):
    """Updates Jellyfin integration configuration."""
    settings.jellyfin_url = payload.url.strip() if payload.url else None
    settings.jellyfin_api_key = payload.api_key.strip() if payload.api_key else None
    settings.jellyfin_auto_refresh = payload.auto_refresh
    save_config(settings)
    logger.info("Jellyfin settings updated.")
    return payload


@router.post("/test", response_model=JellyfinTestResponse)
async def test_jellyfin_connection(payload: JellyfinConfig, admin=Depends(get_current_admin)):
    """Tests connectivity with Jellyfin media server."""
    result = await jellyfin_service.test_connection(payload.url, payload.api_key)
    return JellyfinTestResponse(
        success=result["success"],
        message=result["message"],
        server_name=result.get("server_name"),
        version=result.get("version"),
    )


@router.post("/refresh")
async def trigger_manual_refresh(admin=Depends(get_current_admin)):
    """Triggers an immediate library refresh scan on Jellyfin."""
    if not settings.jellyfin_url or not settings.jellyfin_api_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Jellyfin is not fully configured (URL and API Key required)."
        )

    success = await jellyfin_service.trigger_library_refresh(settings.jellyfin_url, settings.jellyfin_api_key)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Could not trigger Jellyfin library refresh. Check logs for details."
        )
    return {"status": "success", "message": "Jellyfin library refresh triggered successfully."}
