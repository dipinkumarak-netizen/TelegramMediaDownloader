"""System status and Windows service control API routes."""

import logging
from typing import Dict, Any

from fastapi import APIRouter, HTTPException, status, Depends

from app.api.deps import get_current_admin
from app.db.models import SystemStatusResponse
from app.services.system_service import get_system_metrics

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/system", tags=["System"])


@router.get("/status", response_model=SystemStatusResponse)
async def get_system_status(admin=Depends(get_current_admin)):
    """Returns real-time system performance and OS metrics."""
    metrics = get_system_metrics(service_status="Running")
    return SystemStatusResponse(**metrics)
