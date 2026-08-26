"""Tests for password hashing, session tokens, brute-force rate limiter, and path security."""

import time
from app.core.security import (
    hash_password,
    verify_password,
    generate_session_token,
    is_rate_limited,
    record_failed_login,
    clear_failed_logins,
    is_safe_path,
)


def test_password_hashing():
    pwd = "SuperSecretPassword123!"
    hashed = hash_password(pwd)
    
    assert hashed != pwd
    assert verify_password(pwd, hashed) is True
    assert verify_password("WrongPassword", hashed) is False

    # Test Argon2 verification
    argon2_hash = "$argon2id$v=19$m=65536,t=3,p=4$fgEXKlYYI1PKsfxG6qZLkg$pYPYxEZw40PGRUeQLSGuUpnxQ1VskX7Q1r8WoEkIFoU"
    assert verify_password("wrong_test_pwd", argon2_hash) is False


def test_session_token_generation():
    token1 = generate_session_token()
    token2 = generate_session_token()
    
    assert len(token1) >= 48
    assert token1 != token2


def test_brute_force_rate_limiter():
    test_ip = "192.168.1.99"
    clear_failed_logins(test_ip)

    # 4 failed attempts: not yet limited
    for _ in range(4):
        record_failed_login(test_ip)
        limited, _ = is_rate_limited(test_ip)
        assert limited is False

    # 5th failed attempt: limited
    record_failed_login(test_ip)
    limited, remaining = is_rate_limited(test_ip)
    assert limited is True
    assert remaining > 0

    # Clear on success
    clear_failed_logins(test_ip)
    limited, _ = is_rate_limited(test_ip)
    assert limited is False


def test_path_traversal_safety(tmp_path):
    base_dir = tmp_path / "downloads"
    base_dir.mkdir()

    safe_target = base_dir / "movie.mkv"
    unsafe_target = tmp_path / "outside.txt"
    traversal_target = base_dir / ".." / "outside.txt"

    assert is_safe_path(str(base_dir), str(safe_target)) is True
    assert is_safe_path(str(base_dir), str(unsafe_target)) is False
    assert is_safe_path(str(base_dir), str(traversal_target)) is False
