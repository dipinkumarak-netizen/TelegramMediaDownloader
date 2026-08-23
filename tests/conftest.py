"""Test fixtures, temporary test environments, and database initialization."""

import os
import shutil
import tempfile
from pathlib import Path
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport

# Set test environment before imports
os.environ["TELEGRAM_DOWNLOADER_LOG_LEVEL"] = "WARNING"
os.environ["TELEGRAM_DOWNLOADER_IS_PRODUCTION"] = "false"

from app.config import settings
from app.db.database import set_database_path
from app.db.migrations import run_migrations
from app.main import create_app


@pytest.fixture(scope="session", autouse=True)
def test_env():
    """Sets up a clean temporary AppData directory for the entire test session."""
    temp_dir = Path(tempfile.mkdtemp(prefix="tg_downloader_test_"))
    settings.data_dir = temp_dir
    settings.ensure_directories()
    
    test_db = temp_dir / "database" / "test.db"
    set_database_path(test_db)
    run_migrations()

    yield temp_dir

    # Cleanup after tests
    try:
        shutil.rmtree(temp_dir)
    except Exception:
        pass


@pytest_asyncio.fixture
async def client():
    """Creates an async HTTP test client against the FastAPI application."""
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac
