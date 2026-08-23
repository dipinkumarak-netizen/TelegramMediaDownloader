"""Security, password hashing, session tokens, and brute-force protection."""

import hashlib
import hmac
import os
import secrets
import time
from collections import defaultdict
from typing import Dict, Optional, Tuple

import bcrypt

# In-memory brute force protection tracking: IP -> list of failed timestamps
_FAILED_LOGIN_ATTEMPTS: Dict[str, list] = defaultdict(list)
_LOCKOUT_DURATION_SECONDS = 15 * 60  # 15 minutes
_MAX_FAILED_ATTEMPTS = 5
_WINDOW_SECONDS = 5 * 60  # 5 minutes window


def hash_password(password: str) -> str:
    """Hashes a plaintext password securely using direct bcrypt with salt."""
    pwd_bytes = password.encode("utf-8")[:72]  # bcrypt standard limit
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(pwd_bytes, salt).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifies a plaintext password against a stored bcrypt hash."""
    try:
        pwd_bytes = plain_password.encode("utf-8")[:72]
        hash_bytes = hashed_password.encode("utf-8")
        return bcrypt.checkpw(pwd_bytes, hash_bytes)
    except Exception:
        return False


def generate_session_token() -> str:
    """Generates a cryptographically secure random session token."""
    return secrets.token_urlsafe(48)


def is_rate_limited(ip_address: str) -> Tuple[bool, int]:
    """Checks if the client IP is currently rate-limited due to failed attempts.
    
    Returns (is_limited, remaining_lockout_seconds).
    """
    now = time.time()
    attempts = _FAILED_LOGIN_ATTEMPTS.get(ip_address, [])
    
    # Filter attempts within the window
    recent_attempts = [t for t in attempts if now - t < _LOCKOUT_DURATION_SECONDS]
    _FAILED_LOGIN_ATTEMPTS[ip_address] = recent_attempts
    
    if len(recent_attempts) >= _MAX_FAILED_ATTEMPTS:
        newest = max(recent_attempts)
        remaining = int(_LOCKOUT_DURATION_SECONDS - (now - newest))
        if remaining > 0:
            return True, remaining
            
    return False, 0


def record_failed_login(ip_address: str) -> None:
    """Records a failed login attempt for an IP address."""
    _FAILED_LOGIN_ATTEMPTS[ip_address].append(time.time())


def clear_failed_logins(ip_address: str) -> None:
    """Clears failed login attempts for an IP address upon successful login."""
    if ip_address in _FAILED_LOGIN_ATTEMPTS:
        del _FAILED_LOGIN_ATTEMPTS[ip_address]


def is_safe_path(base_dir: str, target_path: str) -> bool:
    """Verifies that target_path is within base_dir to prevent directory traversal attacks."""
    try:
        base = os.path.abspath(base_dir)
        target = os.path.abspath(target_path)
        return os.path.commonpath([base]) == os.path.commonpath([base, target])
    except Exception:
        return False
