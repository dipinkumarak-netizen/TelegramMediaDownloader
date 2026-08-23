"""API dependencies, authentication validators, and context injection."""

import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any

from fastapi import Request, HTTPException, status, Depends
from fastapi.security import APIKeyCookie, HTTPBearer, HTTPAuthorizationCredentials

from app.db.database import db
from app.db.models import AdminUser

logger = logging.getLogger(__name__)

cookie_sec = APIKeyCookie(name="tg_session", auto_error=False)
bearer_sec = HTTPBearer(auto_error=False)


async def get_current_admin(
    request: Request,
    cookie_token: Optional[str] = Depends(cookie_sec),
    bearer_token: Optional[HTTPAuthorizationCredentials] = Depends(bearer_sec),
) -> AdminUser:
    """Authenticates admin user from session cookie or Authorization Bearer header."""
    token = None
    if cookie_token:
        token = cookie_token
    elif bearer_token:
        token = bearer_token.credentials

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Please sign in.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    query = """
        SELECT s.token, s.user_id, s.expires_at, a.id, a.username, a.created_at, a.last_login
        FROM sessions s
        JOIN admins a ON s.user_id = a.id
        WHERE s.token = ? AND datetime(s.expires_at) > datetime('now');
    """
    row = await db.fetch_one(query, (token,))
    if not row:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session has expired or is invalid. Please sign in again.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return AdminUser(
        id=row["id"],
        username=row["username"],
        created_at=str(row["created_at"]),
        last_login=str(row["last_login"]) if row["last_login"] else None,
    )
