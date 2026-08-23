"""Telegram source channels, groups, and chats management API routes."""

import logging
from typing import List, Dict, Any

from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel

from app.api.deps import get_current_admin
from app.db.models import SourceCreate, SourceUpdate, SourceResponse
from app.services.source_manager import source_manager
from app.services.telegram_service import telegram_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/sources", tags=["Sources"])


class TestSourceRequest(BaseModel):
    telegram_id: str


@router.get("", response_model=List[SourceResponse])
async def list_sources(admin=Depends(get_current_admin)):
    """Returns all registered Telegram sources."""
    sources = await source_manager.get_all_sources()
    return [
        SourceResponse(
            id=s["id"],
            telegram_id=s["telegram_id"],
            title=s["title"],
            username=s["username"],
            source_type=s["source_type"],
            is_enabled=bool(s["is_enabled"]),
            download_videos=bool(s["download_videos"]),
            download_documents=bool(s["download_documents"]),
            download_audio=bool(s["download_audio"]),
            download_images=bool(s["download_images"]),
            download_archives=bool(s["download_archives"]),
            min_size_bytes=s["min_size_bytes"],
            max_size_bytes=s["max_size_bytes"],
            custom_subfolder=s["custom_subfolder"],
            created_at=str(s["created_at"]),
            updated_at=str(s["updated_at"]),
        )
        for s in sources
    ]


@router.post("", response_model=SourceResponse)
async def create_source(payload: SourceCreate, admin=Depends(get_current_admin)):
    """Registers a new Telegram source for media monitoring."""
    try:
        source = await source_manager.add_source(payload)
        return SourceResponse(
            id=source["id"],
            telegram_id=source["telegram_id"],
            title=source["title"],
            username=source["username"],
            source_type=source["source_type"],
            is_enabled=bool(source["is_enabled"]),
            download_videos=bool(source["download_videos"]),
            download_documents=bool(source["download_documents"]),
            download_audio=bool(source["download_audio"]),
            download_images=bool(source["download_images"]),
            download_archives=bool(source["download_archives"]),
            min_size_bytes=source["min_size_bytes"],
            max_size_bytes=source["max_size_bytes"],
            custom_subfolder=source["custom_subfolder"],
            created_at=str(source["created_at"]),
            updated_at=str(source["updated_at"]),
        )
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except Exception as e:
        logger.error(f"Error adding Telegram source: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to add source: {str(e)}")


@router.get("/{source_id}", response_model=SourceResponse)
async def get_source(source_id: int, admin=Depends(get_current_admin)):
    """Fetches details for a single source."""
    source = await source_manager.get_source_by_id(source_id)
    if not source:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source not found.")
    return SourceResponse(
        id=source["id"],
        telegram_id=source["telegram_id"],
        title=source["title"],
        username=source["username"],
        source_type=source["source_type"],
        is_enabled=bool(source["is_enabled"]),
        download_videos=bool(source["download_videos"]),
        download_documents=bool(source["download_documents"]),
        download_audio=bool(source["download_audio"]),
        download_images=bool(source["download_images"]),
        download_archives=bool(source["download_archives"]),
        min_size_bytes=source["min_size_bytes"],
        max_size_bytes=source["max_size_bytes"],
        custom_subfolder=source["custom_subfolder"],
        created_at=str(source["created_at"]),
        updated_at=str(source["updated_at"]),
    )


@router.put("/{source_id}", response_model=SourceResponse)
async def update_source(source_id: int, payload: SourceUpdate, admin=Depends(get_current_admin)):
    """Updates configuration or filters for an existing source."""
    source = await source_manager.update_source(source_id, payload)
    if not source:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source not found.")
    return SourceResponse(
        id=source["id"],
        telegram_id=source["telegram_id"],
        title=source["title"],
        username=source["username"],
        source_type=source["source_type"],
        is_enabled=bool(source["is_enabled"]),
        download_videos=bool(source["download_videos"]),
        download_documents=bool(source["download_documents"]),
        download_audio=bool(source["download_audio"]),
        download_images=bool(source["download_images"]),
        download_archives=bool(source["download_archives"]),
        min_size_bytes=source["min_size_bytes"],
        max_size_bytes=source["max_size_bytes"],
        custom_subfolder=source["custom_subfolder"],
        created_at=str(source["created_at"]),
        updated_at=str(source["updated_at"]),
    )


@router.delete("/{source_id}")
async def delete_source(source_id: int, admin=Depends(get_current_admin)):
    """Removes a source from monitoring."""
    deleted = await source_manager.delete_source(source_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source not found.")
    return {"status": "success", "message": "Source removed successfully."}


@router.post("/test")
async def test_resolve_source(payload: TestSourceRequest, admin=Depends(get_current_admin)):
    """Resolves entity info from Telegram to verify target before adding."""
    if not telegram_service.client or not telegram_service.client.is_connected() or telegram_service.state.value != "CONNECTED":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Telegram client must be connected and authorized to test source resolution."
        )

    try:
        info = await telegram_service.resolve_entity_info(payload.telegram_id)
        return {"success": True, "data": info}
    except Exception as e:
        return {"success": False, "message": f"Could not resolve Telegram entity: {str(e)}"}
