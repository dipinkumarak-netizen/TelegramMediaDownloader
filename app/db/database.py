"""SQLite Database connection manager with WAL mode and thread-safe async helpers."""

import asyncio
import logging
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from app.constants import DATABASE_DIR, DATABASE_FILE_PATH

logger = logging.getLogger(__name__)

_DB_PATH: Path = DATABASE_FILE_PATH


def set_database_path(path: Path) -> None:
    """Sets a custom database path (used for testing or custom data dir)."""
    global _DB_PATH
    _DB_PATH = path


def get_db_connection() -> sqlite3.Connection:
    """Creates a configured SQLite connection with WAL mode and Row factory."""
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(
        str(_DB_PATH),
        timeout=15.0,
        check_same_thread=False
    )
    conn.row_factory = sqlite3.Row
    
    # Configure SQLite performance and integrity
    cursor = conn.cursor()
    cursor.execute("PRAGMA journal_mode = WAL;")
    cursor.execute("PRAGMA synchronous = NORMAL;")
    cursor.execute("PRAGMA foreign_keys = ON;")
    cursor.execute("PRAGMA busy_timeout = 5000;")
    cursor.close()
    
    return conn


@contextmanager
def get_db():
    """Context manager for synchronous database operations with automatic commit/rollback."""
    conn = get_db_connection()
    try:
        yield conn
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()


class AsyncDatabase:
    """Async wrapper executing SQLite statements via worker threads to prevent blocking event loop."""

    @staticmethod
    def _execute(query: str, params: Tuple = ()) -> int:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            return cursor.rowcount

    @staticmethod
    def _execute_insert(query: str, params: Tuple = ()) -> int:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            return cursor.lastrowid or 0

    @staticmethod
    def _fetch_one(query: str, params: Tuple = ()) -> Optional[Dict[str, Any]]:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            row = cursor.fetchone()
            return dict(row) if row else None

    @staticmethod
    def _fetch_all(query: str, params: Tuple = ()) -> List[Dict[str, Any]]:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            rows = cursor.fetchall()
            return [dict(row) for row in rows]

    @classmethod
    async def execute(cls, query: str, params: Tuple = ()) -> int:
        return await asyncio.to_thread(cls._execute, query, params)

    @classmethod
    async def execute_insert(cls, query: str, params: Tuple = ()) -> int:
        return await asyncio.to_thread(cls._execute_insert, query, params)

    @classmethod
    async def fetch_one(cls, query: str, params: Tuple = ()) -> Optional[Dict[str, Any]]:
        return await asyncio.to_thread(cls._fetch_one, query, params)

    @classmethod
    async def fetch_all(cls, query: str, params: Tuple = ()) -> List[Dict[str, Any]]:
        return await asyncio.to_thread(cls._fetch_all, query, params)


db = AsyncDatabase()
