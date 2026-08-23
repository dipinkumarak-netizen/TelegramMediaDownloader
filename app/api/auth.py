"""Authentication, first-run setup wizard, and session management API routes."""

import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, Any

from fastapi import APIRouter, Request, Response, HTTPException, status, Depends

from app import __version__
from app.config import settings, save_config
from app.core.security import (
    hash_password,
    verify_password,
    generate_session_token,
    is_rate_limited,
    record_failed_login,
    clear_failed_logins,
)
from app.core.storage import validate_storage_path
from app.db.database import db
from app.db.models import (
    SetupStatusResponse,
    SetupWizardRequest,
    LoginRequest,
    AdminUser,
    UserResponse,
)
from app.api.deps import get_current_admin
from app.services.telegram_service import telegram_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/auth", tags=["Authentication"])


async def is_system_initialized() -> bool:
    """Checks if at least one admin user exists in the database."""
    admin = await db.fetch_one("SELECT id FROM admins LIMIT 1;")
    return admin is not None


@router.get("/setup-status", response_model=SetupStatusResponse)
async def get_setup_status():
    """Returns whether initial first-run setup has been completed."""
    initialized = await is_system_initialized()
    return SetupStatusResponse(
        is_setup_completed=initialized,
        version=__version__,
        data_dir=str(settings.data_dir),
        download_dir=settings.download_dir,
        is_telegram_configured=bool(settings.telegram_api_id and settings.telegram_api_hash),
        is_telegram_authenticated=bool(telegram_service.state.value == "CONNECTED"),
    )


@router.post("/setup")
async def execute_setup_wizard(payload: SetupWizardRequest, request: Request, response: Response):
    """Initializes first administrator account and initial application configuration."""
    if await is_system_initialized():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Application has already been configured. Please sign in as administrator.",
        )

    # 1. Validate Download Path
    valid_storage, storage_msg = validate_storage_path(payload.download_dir)
    if not valid_storage:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=storage_msg)

    # 2. Create Admin Account
    hashed_pwd = hash_password(payload.password)
    insert_admin_query = "INSERT INTO admins (username, password_hash) VALUES (?, ?);"
    admin_id = await db.execute_insert(insert_admin_query, (payload.username.strip(), hashed_pwd))

    # 3. Update Settings
    settings.download_dir = payload.download_dir.strip()

    if payload.telegram_api_id and payload.telegram_api_hash:
        settings.telegram_api_id = payload.telegram_api_id
        settings.telegram_api_hash = payload.telegram_api_hash.strip()
        settings.telegram_phone = payload.telegram_phone.strip() if payload.telegram_phone else None

    if payload.jellyfin_url:
        settings.jellyfin_url = payload.jellyfin_url.strip()
        settings.jellyfin_api_key = payload.jellyfin_api_key.strip() if payload.jellyfin_api_key else None
        settings.jellyfin_auto_refresh = payload.jellyfin_auto_refresh

    save_config(settings)

    # 4. Generate Session Token (7 days validity)
    token = generate_session_token()
    expires_at = (datetime.now(timezone.utc) + timedelta(days=7)).strftime("%Y-%m-%d %H:%M:%S")
    client_ip = request.client.host if request.client else "unknown"
    user_agent = request.headers.get("User-Agent", "unknown")

    await db.execute(
        "INSERT INTO sessions (token, user_id, expires_at, ip_address, user_agent) VALUES (?, ?, ?, ?, ?);",
        (token, admin_id, expires_at, client_ip, user_agent)
    )

    # Set secure HttpOnly session cookie
    response.set_cookie(
        key="tg_session",
        value=token,
        httponly=True,
        samesite="lax",
        max_age=7 * 86400,
        secure=False,  # Allow LAN HTTP
    )

    logger.info(f"Initial setup wizard completed successfully. Admin '{payload.username}' registered.")
    return {
        "status": "success",
        "message": "Initial setup completed successfully.",
        "token": token,
        "username": payload.username,
    }


@router.post("/login")
async def login(payload: LoginRequest, request: Request, response: Response):
    """Authenticates admin user and creates a secure session."""
    client_ip = request.client.host if request.client else "127.0.0.1"

    # Check brute force rate limit
    is_limited, remaining = is_rate_limited(client_ip)
    if is_limited:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Too many failed login attempts. Please wait {remaining} seconds before trying again.",
        )

    admin = await db.fetch_one("SELECT * FROM admins WHERE username = ?;", (payload.username.strip(),))
    if not admin or not verify_password(payload.password, admin["password_hash"]):
        record_failed_login(client_ip)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password.",
        )

    clear_failed_logins(client_ip)

    # Update last login timestamp
    await db.execute("UPDATE admins SET last_login = CURRENT_TIMESTAMP WHERE id = ?;", (admin["id"],))

    # Generate Session
    token = generate_session_token()
    expires_at = (datetime.now(timezone.utc) + timedelta(days=7)).strftime("%Y-%m-%d %H:%M:%S")
    user_agent = request.headers.get("User-Agent", "unknown")

    await db.execute(
        "INSERT INTO sessions (token, user_id, expires_at, ip_address, user_agent) VALUES (?, ?, ?, ?, ?);",
        (token, admin["id"], expires_at, client_ip, user_agent)
    )

    response.set_cookie(
        key="tg_session",
        value=token,
        httponly=True,
        samesite="lax",
        max_age=7 * 86400,
        secure=False,
    )

    logger.info(f"Admin '{admin['username']}' logged in from {client_ip}.")
    return {
        "status": "success",
        "message": "Signed in successfully.",
        "token": token,
        "username": admin["username"],
    }


@router.post("/logout")
async def logout(request: Request, response: Response):
    """Terminates active session and clears auth cookies."""
    token = request.cookies.get("tg_session")
    if not token and (auth_header := request.headers.get("Authorization")):
        if auth_header.startswith("Bearer "):
            token = auth_header.split(" ", 1)[1]

    if token:
        await db.execute("DELETE FROM sessions WHERE token = ?;", (token,))

    response.delete_cookie(key="tg_session")
    return {"status": "success", "message": "Signed out successfully."}


@router.get("/me", response_model=UserResponse)
async def get_current_user_profile(admin: AdminUser = Depends(get_current_admin)):
    """Returns current user authentication profile."""
    return UserResponse(
        username=admin.username,
        is_authenticated=True,
    )
