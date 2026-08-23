"""Database migrations runner for schema initialization and version management."""

import logging
from app.db.database import get_db

logger = logging.getLogger(__name__)

MIGRATION_V1 = """
-- Schema version tracking
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY,
    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Admin users table
CREATE TABLE IF NOT EXISTS admins (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP
);

-- Active authenticated sessions
CREATE TABLE IF NOT EXISTS sessions (
    token TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES admins(id) ON DELETE CASCADE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP NOT NULL,
    ip_address TEXT,
    user_agent TEXT
);

-- Monitored Telegram channels, groups, and sources
CREATE TABLE IF NOT EXISTS telegram_sources (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_id TEXT UNIQUE NOT NULL,
    title TEXT NOT NULL,
    username TEXT,
    source_type TEXT NOT NULL DEFAULT 'CHANNEL',
    is_enabled BOOLEAN NOT NULL DEFAULT 1,
    download_videos BOOLEAN NOT NULL DEFAULT 1,
    download_documents BOOLEAN NOT NULL DEFAULT 1,
    download_audio BOOLEAN NOT NULL DEFAULT 1,
    download_images BOOLEAN NOT NULL DEFAULT 0,
    download_archives BOOLEAN NOT NULL DEFAULT 1,
    min_size_bytes INTEGER NOT NULL DEFAULT 0,
    max_size_bytes INTEGER NOT NULL DEFAULT 0,
    custom_subfolder TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Persistent download jobs queue
CREATE TABLE IF NOT EXISTS downloads (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_chat_id TEXT NOT NULL,
    telegram_message_id INTEGER NOT NULL,
    source_title TEXT,
    filename TEXT NOT NULL,
    sanitized_filename TEXT NOT NULL,
    destination_path TEXT NOT NULL,
    temp_path TEXT,
    file_size INTEGER NOT NULL DEFAULT 0,
    mime_type TEXT,
    status TEXT NOT NULL DEFAULT 'QUEUED',
    progress_percent REAL NOT NULL DEFAULT 0.0,
    downloaded_bytes INTEGER NOT NULL DEFAULT 0,
    speed_bytes_per_sec REAL NOT NULL DEFAULT 0.0,
    retry_count INTEGER NOT NULL DEFAULT 0,
    max_retries INTEGER NOT NULL DEFAULT 3,
    error_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    UNIQUE(telegram_chat_id, telegram_message_id)
);

-- Key-value settings storage
CREATE TABLE IF NOT EXISTS settings_store (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Performance Indexes
CREATE INDEX IF NOT EXISTS idx_downloads_status ON downloads(status);
CREATE INDEX IF NOT EXISTS idx_downloads_chat_msg ON downloads(telegram_chat_id, telegram_message_id);
CREATE INDEX IF NOT EXISTS idx_sources_enabled ON telegram_sources(is_enabled);
CREATE INDEX IF NOT EXISTS idx_sessions_token ON sessions(token);
CREATE INDEX IF NOT EXISTS idx_sessions_expires ON sessions(expires_at);
"""


def run_migrations() -> None:
    """Applies all pending database migrations cleanly."""
    with get_db() as conn:
        cursor = conn.cursor()
        
        # Ensure schema_version exists
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS schema_version (
                version INTEGER PRIMARY KEY,
                applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        
        cursor.execute("SELECT MAX(version) FROM schema_version;")
        row = cursor.fetchone()
        current_version = row[0] if row and row[0] is not None else 0

        # Migration 1: Initial schema
        if current_version < 1:
            logger.info("Applying database migration v1 (Initial Schema)...")
            cursor.executescript(MIGRATION_V1)
            cursor.execute("INSERT INTO schema_version (version) VALUES (1);")
            logger.info("Database migration v1 applied successfully.")

    logger.info("Database schema is up to date.")
