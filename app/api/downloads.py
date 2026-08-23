"""Download queue and job management API routes."""

import logging
from typing import List, Optional, Dict, Any

from fastapi import APIRouter, HTTPException, status, Depends, Query

from app.api.deps import get_current_admin
from app.db.models import DownloadItem, DownloadsStats
from app.services.download_manager import download_manager

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/downloads", tags=["Downloads"])


@router.get("", response_model=List[DownloadItem])
async def get_downloads(
    status: Optional[str] = Query(None, description="Filter by status (QUEUED, DOWNLOADING, COMPLETED, FAILED, CANCELLED, RETRYING)"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    admin=Depends(get_current_admin)
):
    """Retrieves list of download jobs with pagination and status filtering."""
    downloads = await download_manager.get_downloads_list(status=status, limit=limit, offset=offset)
    return [DownloadItem(**d) for d in downloads]


@router.get("/stats", response_model=DownloadsStats)
async def get_download_stats(admin=Depends(get_current_admin)):
    """Retrieves download queue statistics and real-time aggregate speed."""
    stats = await download_manager.get_stats()
    return DownloadsStats(**stats)


@router.post("/{download_id}/cancel")
async def cancel_download(download_id: int, admin=Depends(get_current_admin)):
    """Cancels a pending or currently active download job."""
    success = await download_manager.cancel_job(download_id)
    if not success:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Could not cancel job (it may already be completed or cancelled).")
    return {"status": "success", "message": f"Download #{download_id} cancelled."}


@router.post("/{download_id}/retry")
async def retry_download(download_id: int, admin=Depends(get_current_admin)):
    """Re-queues a failed or cancelled download job for retry."""
    success = await download_manager.retry_job(download_id)
    if not success:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Job not found or cannot be retried.")
    return {"status": "success", "message": f"Download #{download_id} re-queued for download."}


@router.delete("/{download_id}")
async def delete_download(download_id: int, admin=Depends(get_current_admin)):
    """Removes a download job from history."""
    success = await download_manager.delete_job(download_id)
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found.")
    return {"status": "success", "message": f"Download #{download_id} deleted."}


@router.post("/clear-completed")
async def clear_completed_downloads(admin=Depends(get_current_admin)):
    """Cleans up completed and cancelled jobs from the database history."""
    count = await download_manager.clear_completed_jobs()
    return {"status": "success", "message": f"Cleared {count} completed and cancelled jobs."}
