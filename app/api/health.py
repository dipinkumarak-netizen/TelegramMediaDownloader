"""Health check endpoint for monitoring, load balancers, and external probes."""

import logging
from typing import Dict, Any

from fastapi import APIRouter
from app import __version__
from app.config import settings
from app.db.database import db
from app.services.telegram_service import telegram_service

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Health"])


@router.get("/health")
@router.get("/api/health")
async def health_check():
    """Returns application operational health status in structured JSON."""
    db_ok = False
    try:
        row = await db.fetch_one("SELECT 1 as val;")
        db_ok = bool(row and row["val"] == 1)
    except Exception:
        db_ok = False

    tg_status = telegram_service.state.value

    return {
        "status": "ok" if db_ok else "degraded",
        "service": "telegram-downloader",
        "version": __version__,
        "database": "connected" if db_ok else "error",
        "telegram": tg_status.lower(),
        "storage_configured": bool(settings.download_dir),
    }
