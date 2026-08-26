"""Structured logging with rotating file handler and in-memory log buffer."""

import logging
import os
import sys
from collections import deque
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import List, Dict, Any, Callable
import threading

from app.constants import LOG_FILE_PATH, LOGS_DIR

# Thread-safe in-memory ring buffer for Web UI
_LOG_BUFFER: deque = deque(maxlen=1000)
_LOG_BUFFER_LOCK = threading.Lock()
_LOG_LISTENERS: List[Callable[[Dict[str, Any]], None]] = []
_LISTENERS_LOCK = threading.Lock()


class MemoryLogHandler(logging.Handler):
    """Custom logging handler that buffers recent log entries in memory and notifies listeners."""

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = self.format(record)
            entry = {
                "timestamp": record.created,
                "asctime": self.formatter.formatTime(record, "%Y-%m-%d %H:%M:%S") if self.formatter else "",
                "level": record.levelname,
                "name": record.name,
                "message": record.getMessage(),
                "formatted": msg,
            }
            with _LOG_BUFFER_LOCK:
                _LOG_BUFFER.append(entry)

            with _LISTENERS_LOCK:
                listeners = list(_LOG_LISTENERS)

            for listener in listeners:
                try:
                    listener(entry)
                except Exception:
                    pass
        except Exception:
            self.handleError(record)


def setup_logging(log_level: str = "INFO") -> logging.Logger:
    """Configures the root logger with console, rotating file, and in-memory buffer."""
    # Ensure logs directory exists
    LOGS_DIR.mkdir(parents=True, exist_ok=True)

    numeric_level = getattr(logging, log_level.upper(), logging.INFO)
    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)

    # Avoid duplicate handlers on re-setup
    for handler in list(root_logger.handlers):
        root_logger.removeHandler(handler)

    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # 1. Console Handler (stdout)
    if sys.stdout is not None:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(numeric_level)
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)

    # 2. Rotating File Handler (10MB per file, 5 backups)
    try:
        file_handler = RotatingFileHandler(
            str(LOG_FILE_PATH),
            maxBytes=10 * 1024 * 1024,
            backupCount=5,
            encoding="utf-8"
        )
        file_handler.setLevel(numeric_level)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)
    except Exception as e:
        console_handler.handle(logging.LogRecord(
            "app.core.logger", logging.ERROR, "", 0, f"Failed to initialize file logger: {e}", (), None
        ))

    # 3. In-memory Buffer Handler for Web UI
    mem_handler = MemoryLogHandler()
    mem_handler.setLevel(numeric_level)
    mem_handler.setFormatter(formatter)
    root_logger.addHandler(mem_handler)

    # Reduce verbosity for noisy 3rd party loggers
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("telethon").setLevel(logging.INFO)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)

    logger = logging.getLogger("TelegramDownloader")
    logger.info(f"Logging initialized at level {log_level}. Log file: {LOG_FILE_PATH}")
    return logger


def get_recent_logs(limit: int = 100, level: str = None) -> List[Dict[str, Any]]:
    """Returns recent log entries from memory buffer."""
    with _LOG_BUFFER_LOCK:
        logs = list(_LOG_BUFFER)

    if level and level.upper() != "ALL":
        target = level.upper()
        logs = [entry for entry in logs if entry["level"] == target]

    return logs[-limit:] if limit > 0 else logs


def register_log_listener(listener: Callable[[Dict[str, Any]], None]) -> None:
    """Registers a listener for new log entries."""
    with _LISTENERS_LOCK:
        if listener not in _LOG_LISTENERS:
            _LOG_LISTENERS.append(listener)


def unregister_log_listener(listener: Callable[[Dict[str, Any]], None]) -> None:
    """Unregisters a log listener."""
    with _LISTENERS_LOCK:
        if listener in _LOG_LISTENERS:
            _LOG_LISTENERS.remove(listener)
