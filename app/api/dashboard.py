"""Dashboard aggregate metrics and live statistics API."""

import logging
from typing import Dict, Any

from fastapi import APIRouter, Depends

from app.api.deps import get_current_admin
from app.config import settings
from app.core.storage import get_windows_drives, format_bytes
from app.db.database import db
from app.services.telegram_service import telegram_service
from app.services.download_manager import download_manager
from app.services.system_service import get_system_metrics

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/dashboard", tags=["Dashboard"])


@router.get("/stats")
async def get_dashboard_summary(admin=Depends(get_current_admin)):
    """Returns aggregated summary data for the main dashboard view."""
    # 1. System & Process Metrics
    system_metrics = get_system_metrics(service_status="Running")

    # 2. Telegram Status
    tg_status = telegram_service.get_status()

    # 3. Downloads Stats
    dl_stats = await download_manager.get_stats()

    # 4. Sources Stats
    sources_query = """
        SELECT 
            COUNT(*) as total,
            SUM(CASE WHEN is_enabled = 1 THEN 1 ELSE 0 END) as enabled
        FROM telegram_sources;
    """
    sources_row = await db.fetch_one(sources_query) or {}

    # 5. Storage Stats
    drives = get_windows_drives()
    download_drive_info = None
    if settings.download_dir:
        # Find which drive contains download_dir
        for d in drives:
            if settings.download_dir.upper().startswith(d["device"].upper()) or settings.download_dir.upper().startswith(d["mountpoint"].upper()):
                download_drive_info = d
                break

    # 6. Recent Failed Downloads
    recent_errors = await db.fetch_all(
        """SELECT id, filename, error_message, created_at 
           FROM downloads 
           WHERE status = 'FAILED' AND error_message IS NOT NULL 
           ORDER BY created_at DESC 
           LIMIT 5;"""
    )

    return {
        "system": system_metrics,
        "telegram": tg_status,
        "downloads": dl_stats,
        "sources": {
            "total": sources_row.get("total") or 0,
            "enabled": sources_row.get("enabled") or 0,
        },
        "storage": {
            "download_dir": settings.download_dir,
            "drive": download_drive_info,
            "all_drives": drives,
        },
        "recent_errors": recent_errors,
    }
