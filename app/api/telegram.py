"""Telegram client configuration, authentication, and connection API routes."""

import logging
from typing import Dict, Any

from fastapi import APIRouter, HTTPException, status, Depends

from app.api.deps import get_current_admin
from app.db.models import (
    TelegramConfigPayload,
    TelegramCodePayload,
    TelegramPasswordPayload,
    TelegramStatusResponse,
)
from app.services.telegram_service import telegram_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/telegram", tags=["Telegram"])


@router.get("/status", response_model=TelegramStatusResponse)
async def get_telegram_status(admin=Depends(get_current_admin)):
    """Returns current Telegram connection and authorization status."""
    return telegram_service.get_status()


@router.post("/config")
async def configure_and_send_code(payload: TelegramConfigPayload, admin=Depends(get_current_admin)):
    """Validates Telegram API credentials and requests OTP verification code."""
    try:
        result = await telegram_service.start_auth(
            api_id=payload.api_id,
            api_hash=payload.api_hash,
            phone=payload.phone
        )
        if result["status"] == "ERROR":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=result["message"])
        return result
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except Exception as e:
        logger.error(f"Error configuring Telegram: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Telegram error: {str(e)}")


@router.post("/submit-code")
async def submit_verification_code(payload: TelegramCodePayload, admin=Depends(get_current_admin)):
    """Submits the OTP verification code received via SMS/Telegram."""
    result = await telegram_service.submit_code(payload.phone_code)
    if result["status"] == "ERROR":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=result["message"])
    return result


@router.post("/submit-password")
async def submit_2fa_password(payload: TelegramPasswordPayload, admin=Depends(get_current_admin)):
    """Submits 2FA account password if required."""
    result = await telegram_service.submit_password(payload.password)
    if result["status"] == "ERROR":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=result["message"])
    return result


@router.post("/disconnect")
async def disconnect_telegram(admin=Depends(get_current_admin)):
    """Disconnects the active Telegram MTProto client."""
    return await telegram_service.disconnect()


@router.post("/logout")
async def logout_telegram(admin=Depends(get_current_admin)):
    """Terminates Telegram session and deletes stored credentials."""
    return await telegram_service.log_out()
