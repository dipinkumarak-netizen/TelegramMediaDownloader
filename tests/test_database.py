"""Tests for SQLite migrations, schema tables, and async database wrapper."""

import pytest
from app.db.database import db
from app.db.migrations import run_migrations


@pytest.mark.asyncio
async def test_database_schema_and_version():
    run_migrations()
    
    # Check schema version
    row = await db.fetch_one("SELECT MAX(version) as ver FROM schema_version;")
    assert row is not None
    assert row["ver"] >= 1


@pytest.mark.asyncio
async def test_settings_store():
    # Insert or replace setting
    await db.execute("INSERT OR REPLACE INTO settings_store (key, value) VALUES (?, ?);", ("test_key", "test_value"))
    row = await db.fetch_one("SELECT value FROM settings_store WHERE key = ?;", ("test_key",))
    assert row is not None
    assert row["value"] == "test_value"
