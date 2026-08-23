"""Storage inspection, Windows drives discovery, and folder picker API routes."""

import logging
from typing import Optional, Dict, Any

from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel

from app.api.deps import get_current_admin
from app.config import settings, save_config
from app.core.storage import (
    get_windows_drives,
    validate_storage_path,
    list_directory_nodes,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/storage", tags=["Storage"])


class BrowsePathRequest(BaseModel):
    path: Optional[str] = None


class ValidatePathRequest(BaseModel):
    path: str


class SelectStorageRequest(BaseModel):
    download_dir: str


@router.get("/drives")
async def list_drives(admin=Depends(get_current_admin)):
    """Discovers all available Windows drives with space, filesystem type, and write access."""
    drives = get_windows_drives()
    return {
        "current_download_dir": settings.download_dir,
        "drives": drives,
    }


@router.post("/browse")
async def browse_directory(payload: BrowsePathRequest, admin=Depends(get_current_admin)):
    """Lists directories on the selected drive/path for interactive folder browsing."""
    return list_directory_nodes(payload.path)


@router.post("/validate")
async def validate_path(payload: ValidatePathRequest, admin=Depends(get_current_admin)):
    """Validates if a storage path exists, is writable, and safe."""
    is_valid, message = validate_storage_path(payload.path)
    return {
        "valid": is_valid,
        "message": message,
        "path": payload.path,
    }


@router.post("/select")
async def select_download_directory(payload: SelectStorageRequest, admin=Depends(get_current_admin)):
    """Selects and sets the main download storage directory."""
    is_valid, message = validate_storage_path(payload.download_dir)
    if not is_valid:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=message)

    settings.download_dir = payload.download_dir.strip()
    save_config(settings)
    logger.info(f"Download storage directory updated to: {settings.download_dir}")
    return {
        "status": "success",
        "message": "Download storage directory updated successfully.",
        "download_dir": settings.download_dir,
    }
