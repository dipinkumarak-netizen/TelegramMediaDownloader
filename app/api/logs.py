"""Log retrieval, downloading, and Server-Sent Events (SSE) streaming API routes."""

import asyncio
import json
import logging
from pathlib import Path
from typing import Optional, List, Dict, Any

from fastapi import APIRouter, Query, Depends, HTTPException, status
from fastapi.responses import StreamingResponse, FileResponse

from app.api.deps import get_current_admin
from app.constants import LOG_FILE_PATH
from app.core.logger import (
    get_recent_logs,
    register_log_listener,
    unregister_log_listener,
)
from app.services.download_manager import download_manager

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/logs", tags=["Logs"])


@router.get("")
async def get_logs(
    limit: int = Query(200, ge=1, le=1000),
    level: Optional[str] = Query("ALL"),
    admin=Depends(get_current_admin)
):
    """Retrieves recent application log records from the in-memory buffer."""
    return get_recent_logs(limit=limit, level=level)


@router.get("/download")
async def download_log_file(admin=Depends(get_current_admin)):
    """Downloads the full rotating log file."""
    if not LOG_FILE_PATH.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Log file does not exist yet.")
    return FileResponse(
        path=str(LOG_FILE_PATH),
        filename="telegram_downloader.log",
        media_type="text/plain"
    )


@router.get("/stream")
async def stream_live_events(admin=Depends(get_current_admin)):
    """Server-Sent Events (SSE) endpoint for real-time live log and download updates."""
    event_queue: asyncio.Queue = asyncio.Queue(maxsize=100)
    loop = asyncio.get_running_loop()

    def log_callback(entry: Dict[str, Any]):
        try:
            loop.call_soon_threadsafe(
                event_queue.put_nowait,
                {"type": "log", "data": entry}
            )
        except Exception:
            pass

    def progress_callback(entry: Dict[str, Any]):
        try:
            loop.call_soon_threadsafe(
                event_queue.put_nowait,
                {"type": "download_progress", "data": entry}
            )
        except Exception:
            pass

    register_log_listener(log_callback)
    download_manager.register_progress_listener(progress_callback)

    async def event_generator():
        try:
            # Send initial keepalive
            yield f": connected\n\n"
            while True:
                try:
                    event = await asyncio.wait_for(event_queue.get(), timeout=15.0)
                    yield f"event: {event['type']}\ndata: {json.dumps(event['data'])}\n\n"
                except asyncio.TimeoutError:
                    # Keepalive heartbeat
                    yield f": ping\n\n"
        except asyncio.CancelledError:
            pass
        finally:
            unregister_log_listener(log_callback)
            download_manager.unregister_progress_listener(progress_callback)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )
