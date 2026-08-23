"""Tests for persistent download queue, recovery on restart, and state transitions."""

import pytest
from app.db.database import db
from app.services.download_manager import download_manager


@pytest.mark.asyncio
async def test_queue_lifecycle():
    # Insert test job
    insert_query = """
        INSERT INTO downloads (
            telegram_chat_id, telegram_message_id, source_title,
            filename, sanitized_filename, destination_path,
            file_size, mime_type, status
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'QUEUED');
    """
    job_id = await db.execute_insert(
        insert_query,
        (
            "-100199999999",
            101,
            "Test Channel",
            "test_video.mp4",
            "test_video.mp4",
            "C:\\Downloads\\test_video.mp4",
            1024 * 1024 * 10,
            "video/mp4",
        )
    )
    assert job_id > 0

    # Verify initial stats
    stats = await download_manager.get_stats()
    assert stats["queued"] >= 1

    # Cancel job
    cancelled = await download_manager.cancel_job(job_id)
    assert cancelled is True
    job = await db.fetch_one("SELECT status FROM downloads WHERE id = ?;", (job_id,))
    assert job["status"] == "CANCELLED"

    # Retry job
    retried = await download_manager.retry_job(job_id)
    assert retried is True
    job = await db.fetch_one("SELECT status FROM downloads WHERE id = ?;", (job_id,))
    assert job["status"] == "QUEUED"


@pytest.mark.asyncio
async def test_recovery_on_restart():
    # Simulate a crash where job was in DOWNLOADING state
    insert_query = """
        INSERT INTO downloads (
            telegram_chat_id, telegram_message_id, source_title,
            filename, sanitized_filename, destination_path,
            file_size, mime_type, status
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'DOWNLOADING');
    """
    job_id = await db.execute_insert(
        insert_query,
        (
            "-100188888888",
            202,
            "Interrupted Channel",
            "crashed_video.mkv",
            "crashed_video.mkv",
            "C:\\Downloads\\crashed_video.mkv",
            50000000,
            "video/x-matroska",
        )
    )

    # Run recovery
    await download_manager.recover_interrupted_downloads()

    # Verify job is recovered back to QUEUED
    job = await db.fetch_one("SELECT status, error_message FROM downloads WHERE id = ?;", (job_id,))
    assert job["status"] == "QUEUED"
    assert "resumed" in job["error_message"].lower() or "interrupted" in job["error_message"].lower()
