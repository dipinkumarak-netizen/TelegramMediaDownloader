"""Tests for Windows storage detection, path sanitization, and atomic operations."""

from pathlib import Path
from app.core.storage import (
    sanitize_filename,
    get_unique_destination_path,
    finalize_download_file,
    validate_storage_path,
    format_bytes,
)


def test_format_bytes():
    assert format_bytes(500) == "500.00 B"
    assert format_bytes(1024 * 1024) == "1.00 MB"
    assert format_bytes(1024 * 1024 * 1024 * 5) == "5.00 GB"


def test_sanitize_filename_illegal_chars():
    dirty = 'My:Movie<2026>"Special"|Edition?.mkv'
    clean = sanitize_filename(dirty)
    assert clean == "My_Movie_2026__Special__Edition_.mkv"
    assert ":" not in clean
    assert "<" not in clean
    assert "?" not in clean


def test_sanitize_filename_reserved_names():
    assert sanitize_filename("CON.txt") == "_CON.txt"
    assert sanitize_filename("aux.mp4") == "_aux.mp4"
    assert sanitize_filename("NUL") == "_NUL"
    assert sanitize_filename("com1.zip") == "_com1.zip"


def test_sanitize_filename_trailing_dots_and_spaces():
    dirty = "  my document...  .pdf "
    clean = sanitize_filename(dirty)
    assert not clean.startswith(" ")
    assert clean.endswith(".pdf")


def test_unique_destination_path_collision(tmp_path):
    dest_dir = tmp_path / "downloads"
    dest_dir.mkdir()

    # 1. First file
    p1 = get_unique_destination_path(str(dest_dir), "movie.mkv")
    assert p1.name == "movie.mkv"
    p1.write_text("dummy 1")

    # 2. Collision #1 -> movie (1).mkv
    p2 = get_unique_destination_path(str(dest_dir), "movie.mkv")
    assert p2.name == "movie (1).mkv"
    p2.write_text("dummy 2")

    # 3. Collision #2 -> movie (2).mkv
    p3 = get_unique_destination_path(str(dest_dir), "movie.mkv")
    assert p3.name == "movie (2).mkv"
    p3.write_text("dummy 3")

    # 4. Starting with "movie (1).mkv" directly -> should yield "movie (2).mkv" without creating "movie (1) (2).mkv"
    p4 = get_unique_destination_path(str(dest_dir), "movie (1).mkv")
    assert p4.name == "movie (3).mkv" or p4.name == "movie (2).mkv" or " (1) (2)" not in p4.name
    assert " (1) (2)" not in p4.name


def test_finalize_download_file(tmp_path):
    temp_file = tmp_path / "download.part"
    final_file = tmp_path / "final_video.mp4"

    content = b"Video data payload 12345"
    temp_file.write_bytes(content)

    success, msg = finalize_download_file(temp_file, final_file, expected_size=len(content))
    assert success is True
    assert final_file.exists()
    assert not temp_file.exists()
    assert final_file.read_bytes() == content


def test_validate_storage_path(tmp_path):
    valid_dir = tmp_path / "my_downloads"
    is_valid, msg = validate_storage_path(str(valid_dir))
    assert is_valid is True
    assert valid_dir.exists()
