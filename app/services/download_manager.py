"""Persistent download queue worker pool with atomic file writing and crash recovery."""

import asyncio
import logging
import os
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any, Set, Callable

from app.constants import (
    DownloadStatus,
    TEMP_DIR,
    DEFAULT_MAX_CONCURRENT_DOWNLOADS,
    DEFAULT_DOWNLOAD_CHUNK_SIZE,
)
from app.config import settings
from app.db.database import db
from app.core.storage import (
    format_bytes,
    get_unique_destination_path,
    get_temp_download_path,
    finalize_download_file,
    check_free_space,
)
from app.services.telegram_service import telegram_service
from app.services.source_manager import source_manager
from app.services.jellyfin_service import jellyfin_service
from app.services.fast_telethon import fast_download

logger = logging.getLogger(__name__)


class DownloadManager:
    """Manages persistent download jobs, background worker concurrency, and live progress tracking."""

    def __init__(self):
        self._running = False
        self._workers: List[asyncio.Task] = []
        self._active_downloads: Dict[int, Dict[str, Any]] = {}
        self._active_tasks: Dict[int, asyncio.Task] = {}
        self._queue_event = asyncio.Event()
        self._progress_listeners: List[Callable[[Dict[str, Any]], None]] = []

    async def start(self) -> None:
        """Starts download manager workers and recovers interrupted jobs."""
        if self._running:
            return

        self._running = True
        await self.recover_interrupted_downloads()

        # Register message listener with Telegram service
        telegram_service.register_message_listener(self.handle_new_telegram_message)

        # Spawn worker tasks
        concurrency = settings.max_concurrent_downloads or DEFAULT_MAX_CONCURRENT_DOWNLOADS
        for i in range(concurrency):
            worker_task = asyncio.create_task(self._worker_loop(i + 1))
            self._workers.append(worker_task)

        logger.info(f"Download manager started with {concurrency} concurrent workers.")

    async def stop(self) -> None:
        """Stops all download workers cleanly."""
        self._running = False
        self._queue_event.set()

        # Cancel active downloading tasks
        for task in self._active_tasks.values():
            task.cancel()

        for worker in self._workers:
            worker.cancel()

        self._workers.clear()
        self._active_downloads.clear()
        self._active_tasks.clear()
        logger.info("Download manager stopped.")

    async def recover_interrupted_downloads(self) -> None:
        """Recovers interrupted downloads on server restart/crash."""
        query = """
            UPDATE downloads 
            SET status = 'QUEUED', 
                error_message = 'Interrupted by application restart - resumed automatically'
            WHERE status = 'DOWNLOADING';
        """
        count = await db.execute(query)
        if count > 0:
            logger.info(f"Recovered {count} interrupted download jobs from previous session.")

    async def handle_new_telegram_message(self, event: Any) -> None:
        """Processes incoming Telegram message events and queues media."""
        message = getattr(event, "message", None) or event
        if not message or not getattr(message, "media", None):
            return

        chat_id = str(getattr(message, "chat_id", None) or getattr(event, "chat_id", ""))
        clean_chat_id = chat_id.lstrip("-").lstrip("100")

        # Check if chat is in configured sources
        source = await source_manager.get_source_by_telegram_id(chat_id)
        if not source:
            source = await source_manager.get_source_by_telegram_id(clean_chat_id)
            
        if not source or not source.get("is_enabled", 1):
            return

        should_download, filename, file_size, mime_type = source_manager.inspect_message_media(
            message, source
        )

        if not should_download:
            return

        # Verify destination directory is configured
        download_dir = settings.download_dir
        if not download_dir:
            logger.warning("Telegram media detected but no download directory is configured in settings.")
            return

        dest_folder = Path(download_dir)
        if source.get("custom_subfolder"):
            dest_folder = dest_folder / source["custom_subfolder"].strip()

        dest_folder.mkdir(parents=True, exist_ok=True)
        final_dest_path = get_unique_destination_path(str(dest_folder), filename)

        # Check if already queued or completed
        check_query = "SELECT id, status FROM downloads WHERE telegram_chat_id = ? AND telegram_message_id = ?;"
        existing = await db.fetch_one(check_query, (str(chat_id), message.id))
        if existing:
            if existing["status"] in (DownloadStatus.QUEUED.value, DownloadStatus.DOWNLOADING.value, DownloadStatus.COMPLETED.value):
                return

        # Insert new download job
        insert_query = """
            INSERT INTO downloads (
                telegram_chat_id, telegram_message_id, source_title,
                filename, sanitized_filename, destination_path,
                file_size, mime_type, status, max_retries
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'QUEUED', ?)
            ON CONFLICT(telegram_chat_id, telegram_message_id) 
            DO UPDATE SET status = 'QUEUED', error_message = NULL, progress_percent = 0.0;
        """
        await db.execute(
            insert_query,
            (
                str(chat_id),
                message.id,
                source.get("title") or "Telegram Source",
                filename,
                final_dest_path.name,
                str(final_dest_path),
                file_size,
                mime_type,
                settings.max_retries,
            )
        )

        logger.info(f"Queued media '{final_dest_path.name}' ({format_bytes(file_size)}) from '{source.get('title')}'")
        self._queue_event.set()

    async def _worker_loop(self, worker_id: int) -> None:
        """Background worker loop processing queued downloads."""
        while self._running:
            try:
                job = await self._get_next_queued_job()
                if not job:
                    # Wait for next item to be queued
                    try:
                        await asyncio.wait_for(self._queue_event.wait(), timeout=5.0)
                        self._queue_event.clear()
                    except asyncio.TimeoutError:
                        pass
                    continue

                job_id = job["id"]
                current_task = asyncio.current_task()
                if current_task:
                    self._active_tasks[job_id] = current_task

                try:
                    await self._process_download_job(job)
                finally:
                    self._active_tasks.pop(job_id, None)
                    self._active_downloads.pop(job_id, None)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Unexpected error in download worker #{worker_id}: {e}", exc_info=True)
                await asyncio.sleep(2.0)

    async def _get_next_queued_job(self) -> Optional[Dict[str, Any]]:
        """Atomically retrieves the next eligible queued or retrying job."""
        query = """
            SELECT * FROM downloads 
            WHERE status IN ('QUEUED', 'RETRYING') 
            ORDER BY created_at ASC 
            LIMIT 1;
        """
        job = await db.fetch_one(query)
        if not job:
            return None

        # Lock the job to prevent other workers from picking it up
        update_query = """
            UPDATE downloads 
            SET status = 'DOWNLOADING', started_at = CURRENT_TIMESTAMP, error_message = NULL
            WHERE id = ? AND status IN ('QUEUED', 'RETRYING');
        """
        affected = await db.execute(update_query, (job["id"],))
        if affected == 0:
            return None  # Another worker grabbed it

        job["status"] = DownloadStatus.DOWNLOADING.value
        return job

    async def _process_download_job(self, job: Dict[str, Any]) -> None:
        """Executes the download process for a specific job."""
        job_id = job["id"]
        chat_id = job["telegram_chat_id"]
        message_id = job["telegram_message_id"]
        destination_path = Path(job["destination_path"])
        file_size = job["file_size"]

        logger.info(f"Starting download #{job_id}: '{destination_path.name}' ({format_bytes(file_size)})")

        # 1. Storage free-space check
        has_space, free_bytes, threshold = check_free_space(
            str(destination_path.parent),
            required_bytes=file_size,
            threshold_mb=settings.free_space_threshold_mb
        )
        if not has_space:
            err = f"Insufficient disk space. Free: {format_bytes(free_bytes)}, Required: {format_bytes(file_size + threshold)}"
            await self._mark_failed(job_id, err, retryable=False)
            return

        # 2. Check Telegram connection
        if not telegram_service.client or not telegram_service.client.is_connected():
            await self._mark_failed(job_id, "Telegram client is not connected.", retryable=True)
            return

        # 3. Create temp download path
        TEMP_DIR.mkdir(parents=True, exist_ok=True)
        temp_path = get_temp_download_path(destination_path, temp_dir=TEMP_DIR)
        await db.execute("UPDATE downloads SET temp_path = ? WHERE id = ?;", (str(temp_path), job_id))

        # 4. Initialize progress tracking
        tracker = {
            "id": job_id,
            "filename": destination_path.name,
            "total_bytes": file_size,
            "downloaded_bytes": 0,
            "progress_percent": 0.0,
            "speed_bytes_per_sec": 0.0,
            "last_bytes": 0,
            "last_time": time.time(),
            "last_db_update": time.time(),
        }
        self._active_downloads[job_id] = tracker

        def progress_callback(received_bytes: int, total_bytes: int):
            now = time.time()
            elapsed = now - tracker["last_time"]
            total = total_bytes or file_size or 1

            tracker["downloaded_bytes"] = received_bytes
            tracker["progress_percent"] = round((received_bytes / total) * 100, 1)

            if elapsed >= 0.5:
                delta_bytes = received_bytes - tracker["last_bytes"]
                tracker["speed_bytes_per_sec"] = max(0.0, delta_bytes / elapsed)
                tracker["last_bytes"] = received_bytes
                tracker["last_time"] = now

                # Notify SSE listeners
                self._broadcast_progress(tracker)

                # Persist to DB at throttled interval
                if now - tracker["last_db_update"] >= 2.0:
                    tracker["last_db_update"] = now
                    asyncio.create_task(
                        db.execute(
                            """UPDATE downloads 
                               SET progress_percent = ?, downloaded_bytes = ?, speed_bytes_per_sec = ?
                               WHERE id = ?;""",
                            (tracker["progress_percent"], received_bytes, tracker["speed_bytes_per_sec"], job_id)
                        )
                    )

        try:
            # Fetch the Telegram message entity
            target_chat = int(chat_id) if chat_id.lstrip("-").isdigit() else chat_id
            message = await telegram_service.client.get_messages(target_chat, ids=message_id)
            
            if not message or not message.media:
                await self._mark_failed(job_id, "Message or media no longer exists on Telegram.", retryable=False)
                return

            # Execute high-speed FastTelethon parallel download with fallback
            await fast_download(
                telegram_service.client,
                message,
                out_file=str(temp_path),
                progress_callback=progress_callback,
                workers=settings.download_workers,
            )

            # Finalize file atomically
            success, msg = finalize_download_file(temp_path, destination_path, expected_size=file_size if file_size > 0 else None)
            if not success:
                await self._mark_failed(job_id, f"File finalization error: {msg}", retryable=True)
                return

            # Mark completed
            actual_size = destination_path.stat().st_size if destination_path.exists() else file_size
            await db.execute(
                """UPDATE downloads 
                   SET status = 'COMPLETED', progress_percent = 100.0, 
                       downloaded_bytes = ?, file_size = ?, completed_at = CURRENT_TIMESTAMP, 
                       error_message = NULL, temp_path = NULL
                   WHERE id = ?;""",
                (actual_size, actual_size, job_id)
            )

            logger.info(f"Successfully completed download #{job_id}: '{destination_path.name}' ({format_bytes(actual_size)})")

            # Trigger optional Jellyfin library refresh
            if settings.jellyfin_auto_refresh and settings.jellyfin_url and settings.jellyfin_api_key:
                asyncio.create_task(
                    jellyfin_service.trigger_library_refresh(settings.jellyfin_url, settings.jellyfin_api_key)
                )

        except asyncio.CancelledError:
            logger.warning(f"Download #{job_id} cancelled.")
            await self._mark_cancelled(job_id)
            if temp_path.exists():
                try:
                    temp_path.unlink()
                except Exception:
                    pass
            raise

        except Exception as e:
            logger.error(f"Download #{job_id} failed: {e}", exc_info=True)
            await self._mark_failed(job_id, str(e), retryable=True)
            if temp_path.exists():
                try:
                    temp_path.unlink()
                except Exception:
                    pass

    async def _mark_failed(self, job_id: int, error_message: str, retryable: bool = True) -> None:
        """Handles job failure with retry escalation."""
        job = await db.fetch_one("SELECT retry_count, max_retries FROM downloads WHERE id = ?;", (job_id,))
        if not job:
            return

        retry_count = job["retry_count"]
        max_retries = job["max_retries"]

        if retryable and retry_count < max_retries:
            next_retry = retry_count + 1
            await db.execute(
                """UPDATE downloads 
                   SET status = 'RETRYING', retry_count = ?, error_message = ?, temp_path = NULL
                   WHERE id = ?;""",
                (next_retry, f"Retry {next_retry}/{max_retries}: {error_message}", job_id)
            )
            logger.info(f"Job #{job_id} set to RETRYING ({next_retry}/{max_retries})")
            # Delay before retry
            await asyncio.sleep(settings.retry_delay_seconds)
            self._queue_event.set()
        else:
            await db.execute(
                """UPDATE downloads 
                   SET status = 'FAILED', error_message = ?, temp_path = NULL
                   WHERE id = ?;""",
                (error_message, job_id)
            )
            logger.warning(f"Job #{job_id} marked FAILED: {error_message}")

    async def _mark_cancelled(self, job_id: int) -> None:
        """Marks job as CANCELLED."""
        await db.execute(
            "UPDATE downloads SET status = 'CANCELLED', error_message = 'Cancelled by user', temp_path = NULL WHERE id = ?;",
            (job_id,)
        )

    async def cancel_job(self, job_id: int) -> bool:
        """Cancels a queued or currently downloading job."""
        if task := self._active_tasks.get(job_id):
            task.cancel()
            return True

        count = await db.execute(
            "UPDATE downloads SET status = 'CANCELLED', error_message = 'Cancelled by user' WHERE id = ? AND status IN ('QUEUED', 'RETRYING');",
            (job_id,)
        )
        return count > 0

    async def retry_job(self, job_id: int) -> bool:
        """Manually retries a failed or cancelled job."""
        count = await db.execute(
            """UPDATE downloads 
               SET status = 'QUEUED', retry_count = 0, error_message = NULL, progress_percent = 0.0, downloaded_bytes = 0
               WHERE id = ?;""",
            (job_id,)
        )
        if count > 0:
            self._queue_event.set()
            return True
        return False

    async def delete_job(self, job_id: int) -> bool:
        """Deletes a job from the database."""
        await self.cancel_job(job_id)
        count = await db.execute("DELETE FROM downloads WHERE id = ?;", (job_id,))
        return count > 0

    async def clear_completed_jobs(self) -> int:
        """Clears completed and cancelled jobs from history."""
        return await db.execute("DELETE FROM downloads WHERE status IN ('COMPLETED', 'CANCELLED');")

    async def get_downloads_list(
        self,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """Fetches download jobs with human-formatted sizes and speeds."""
        if status and status.upper() != "ALL":
            query = """
                SELECT * FROM downloads 
                WHERE status = ? 
                ORDER BY created_at DESC 
                LIMIT ? OFFSET ?;
            """
            rows = await db.fetch_all(query, (status.upper(), limit, offset))
        else:
            query = """
                SELECT * FROM downloads 
                ORDER BY 
                    CASE status 
                        WHEN 'DOWNLOADING' THEN 1 
                        WHEN 'QUEUED' THEN 2 
                        WHEN 'RETRYING' THEN 3 
                        ELSE 4 
                    END,
                    created_at DESC 
                LIMIT ? OFFSET ?;
            """
            rows = await db.fetch_all(query, (limit, offset))

        results = []
        for r in rows:
            job_id = r["id"]
            active_info = self._active_downloads.get(job_id)

            downloaded = active_info["downloaded_bytes"] if active_info else r["downloaded_bytes"]
            speed = active_info["speed_bytes_per_sec"] if active_info else r["speed_bytes_per_sec"]
            progress = active_info["progress_percent"] if active_info else r["progress_percent"]

            total_size = r["file_size"]
            eta = None
            if speed > 0 and total_size > downloaded:
                eta = int((total_size - downloaded) / speed)

            results.append({
                "id": r["id"],
                "telegram_chat_id": r["telegram_chat_id"],
                "telegram_message_id": r["telegram_message_id"],
                "source_title": r["source_title"],
                "filename": r["filename"],
                "sanitized_filename": r["sanitized_filename"],
                "destination_path": r["destination_path"],
                "file_size": total_size,
                "file_size_formatted": format_bytes(total_size),
                "mime_type": r["mime_type"],
                "status": r["status"],
                "progress_percent": progress,
                "downloaded_bytes": downloaded,
                "downloaded_formatted": format_bytes(downloaded),
                "speed_bytes_per_sec": speed,
                "speed_formatted": f"{format_bytes(int(speed))}/s" if speed > 0 else "0 B/s",
                "eta_seconds": eta,
                "retry_count": r["retry_count"],
                "max_retries": r["max_retries"],
                "error_message": r["error_message"],
                "created_at": str(r["created_at"]),
                "started_at": str(r["started_at"]) if r["started_at"] else None,
                "completed_at": str(r["completed_at"]) if r["completed_at"] else None,
            })
        return results

    async def get_stats(self) -> Dict[str, Any]:
        """Calculates download queue aggregate counts and current total bandwidth."""
        query = """
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN status = 'QUEUED' THEN 1 ELSE 0 END) as queued,
                SUM(CASE WHEN status = 'DOWNLOADING' THEN 1 ELSE 0 END) as downloading,
                SUM(CASE WHEN status = 'COMPLETED' THEN 1 ELSE 0 END) as completed,
                SUM(CASE WHEN status = 'FAILED' THEN 1 ELSE 0 END) as failed,
                SUM(CASE WHEN status = 'CANCELLED' THEN 1 ELSE 0 END) as cancelled,
                SUM(CASE WHEN status = 'RETRYING' THEN 1 ELSE 0 END) as retrying,
                SUM(CASE WHEN status = 'COMPLETED' THEN file_size ELSE downloaded_bytes END) as total_downloaded_bytes
            FROM downloads;
        """
        row = await db.fetch_one(query) or {}

        # Current aggregated speed
        current_speed = sum(d.get("speed_bytes_per_sec", 0.0) for d in self._active_downloads.values())
        total_downloaded = row.get("total_downloaded_bytes") or 0

        return {
            "total": row.get("total") or 0,
            "queued": row.get("queued") or 0,
            "downloading": row.get("downloading") or 0,
            "completed": row.get("completed") or 0,
            "failed": row.get("failed") or 0,
            "cancelled": row.get("cancelled") or 0,
            "retrying": row.get("retrying") or 0,
            "total_downloaded_bytes": total_downloaded,
            "total_downloaded_formatted": format_bytes(total_downloaded),
            "current_speed_bytes_per_sec": current_speed,
            "current_speed_formatted": f"{format_bytes(int(current_speed))}/s" if current_speed > 0 else "0 B/s",
        }

    def register_progress_listener(self, listener: Callable[[Dict[str, Any]], None]) -> None:
        """Registers a listener callback for real-time download progress broadcasting."""
        if listener not in self._progress_listeners:
            self._progress_listeners.append(listener)

    def unregister_progress_listener(self, listener: Callable[[Dict[str, Any]], None]) -> None:
        """Unregisters a progress listener."""
        if listener in self._progress_listeners:
            self._progress_listeners.remove(listener)

    def _broadcast_progress(self, data: Dict[str, Any]) -> None:
        """Broadcasts active download progress to registered listeners."""
        for listener in list(self._progress_listeners):
            try:
                listener(data)
            except Exception:
                pass


download_manager = DownloadManager()
