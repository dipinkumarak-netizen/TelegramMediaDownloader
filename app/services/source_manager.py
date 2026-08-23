"""Telegram source channels and groups management with media type filtering."""

import logging
from typing import Dict, List, Optional, Tuple, Any, Set
from telethon.tl.types import (
    MessageMediaDocument,
    MessageMediaPhoto,
    DocumentAttributeFilename,
    DocumentAttributeVideo,
    DocumentAttributeAudio,
)

from app.db.database import db
from app.db.models import SourceCreate, SourceUpdate
from app.services.telegram_service import telegram_service

logger = logging.getLogger(__name__)

ARCHIVE_EXTENSIONS = {".zip", ".rar", ".7z", ".tar", ".gz", ".bz2", ".xz", ".iso"}
VIDEO_EXTENSIONS = {".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".webm", ".m4v", ".ts"}
AUDIO_EXTENSIONS = {".mp3", ".flac", ".wav", ".aac", ".ogg", ".m4a", ".wma", ".opus"}
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif", ".tiff"}


class SourceManager:
    """Manages monitored Telegram sources and validates message filter rules."""

    async def get_all_sources(self) -> List[Dict[str, Any]]:
        """Fetches all registered Telegram sources."""
        query = "SELECT * FROM telegram_sources ORDER BY created_at DESC;"
        return await db.fetch_all(query)

    async def get_source_by_id(self, source_id: int) -> Optional[Dict[str, Any]]:
        """Fetches a specific source by its database ID."""
        query = "SELECT * FROM telegram_sources WHERE id = ?;"
        return await db.fetch_one(query, (source_id,))

    async def get_source_by_telegram_id(self, telegram_id: str) -> Optional[Dict[str, Any]]:
        """Fetches a specific source by its Telegram ID/Chat ID."""
        clean_id = str(telegram_id).lstrip("-").lstrip("100")
        query = """
            SELECT * FROM telegram_sources 
            WHERE telegram_id = ? 
               OR telegram_id = ? 
               OR telegram_id = ?
               OR telegram_id = ?;
        """
        return await db.fetch_one(
            query,
            (
                str(telegram_id),
                f"-{telegram_id}",
                f"-100{clean_id}",
                f"{clean_id}"
            )
        )

    async def get_enabled_source_ids(self) -> Set[str]:
        """Returns set of all enabled source Telegram IDs for quick lookup."""
        query = "SELECT telegram_id FROM telegram_sources WHERE is_enabled = 1;"
        rows = await db.fetch_all(query)
        result = set()
        for r in rows:
            raw_id = str(r["telegram_id"])
            result.add(raw_id)
            clean = raw_id.lstrip("-").lstrip("100")
            result.add(clean)
            result.add(f"-100{clean}")
        return result

    async def add_source(self, data: SourceCreate) -> Dict[str, Any]:
        """Resolves source entity and inserts it into database."""
        resolved_id = data.telegram_id.strip()
        resolved_title = data.title or resolved_id
        resolved_username = None
        source_type = data.source_type.value if hasattr(data.source_type, "value") else str(data.source_type)

        # Attempt to fetch live entity details from Telegram if available
        if telegram_service.client and telegram_service.client.is_connected() and telegram_service.state.value == "CONNECTED":
            try:
                info = await telegram_service.resolve_entity_info(resolved_id)
                resolved_id = info["telegram_id"]
                resolved_title = data.title or info["title"]
                resolved_username = info.get("username")
                source_type = info.get("source_type", source_type)
            except Exception as e:
                logger.warning(f"Could not auto-resolve entity for '{resolved_id}': {e}. Using provided data.")

        # Check for duplicates
        existing = await self.get_source_by_telegram_id(resolved_id)
        if existing:
            raise ValueError(f"A source with Telegram ID '{resolved_id}' is already registered.")

        query = """
            INSERT INTO telegram_sources (
                telegram_id, title, username, source_type, is_enabled,
                download_videos, download_documents, download_audio, download_images, download_archives,
                min_size_bytes, max_size_bytes, custom_subfolder
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """
        params = (
            resolved_id,
            resolved_title,
            resolved_username,
            source_type,
            1 if data.is_enabled else 0,
            1 if data.download_videos else 0,
            1 if data.download_documents else 0,
            1 if data.download_audio else 0,
            1 if data.download_images else 0,
            1 if data.download_archives else 0,
            data.min_size_bytes or 0,
            data.max_size_bytes or 0,
            data.custom_subfolder.strip() if data.custom_subfolder else None,
        )

        new_id = await db.execute_insert(query, params)
        logger.info(f"Added Telegram source '{resolved_title}' (ID: {resolved_id})")
        return await self.get_source_by_id(new_id)

    async def update_source(self, source_id: int, data: SourceUpdate) -> Optional[Dict[str, Any]]:
        """Updates settings and filter configuration for a source."""
        existing = await self.get_source_by_id(source_id)
        if not existing:
            return None

        fields = []
        params = []

        if data.title is not None:
            fields.append("title = ?")
            params.append(data.title.strip())
        if data.is_enabled is not None:
            fields.append("is_enabled = ?")
            params.append(1 if data.is_enabled else 0)
        if data.download_videos is not None:
            fields.append("download_videos = ?")
            params.append(1 if data.download_videos else 0)
        if data.download_documents is not None:
            fields.append("download_documents = ?")
            params.append(1 if data.download_documents else 0)
        if data.download_audio is not None:
            fields.append("download_audio = ?")
            params.append(1 if data.download_audio else 0)
        if data.download_images is not None:
            fields.append("download_images = ?")
            params.append(1 if data.download_images else 0)
        if data.download_archives is not None:
            fields.append("download_archives = ?")
            params.append(1 if data.download_archives else 0)
        if data.min_size_bytes is not None:
            fields.append("min_size_bytes = ?")
            params.append(data.min_size_bytes)
        if data.max_size_bytes is not None:
            fields.append("max_size_bytes = ?")
            params.append(data.max_size_bytes)
        if data.custom_subfolder is not None:
            fields.append("custom_subfolder = ?")
            params.append(data.custom_subfolder.strip() if data.custom_subfolder else None)

        if not fields:
            return existing

        fields.append("updated_at = CURRENT_TIMESTAMP")
        params.append(source_id)

        query = f"UPDATE telegram_sources SET {', '.join(fields)} WHERE id = ?;"
        await db.execute(query, tuple(params))
        return await self.get_source_by_id(source_id)

    async def delete_source(self, source_id: int) -> bool:
        """Deletes a Telegram source from monitoring."""
        query = "DELETE FROM telegram_sources WHERE id = ?;"
        count = await db.execute(query, (source_id,))
        return count > 0

    @staticmethod
    def inspect_message_media(message: Any, source_config: Dict[str, Any]) -> Tuple[bool, str, int, str]:
        """Evaluates whether message media qualifies for download based on source filter rules.
        
        Returns (should_download, filename, file_size, mime_type).
        """
        if not message or not getattr(message, "media", None):
            return False, "", 0, ""

        media = message.media
        filename = ""
        file_size = 0
        mime_type = ""
        is_video = False
        is_audio = False
        is_photo = False
        is_doc = False
        is_archive = False

        if isinstance(media, MessageMediaPhoto):
            is_photo = True
            filename = f"photo_{message.id}.jpg"
            mime_type = "image/jpeg"
            # Photo sizes in Telethon are determined on download or biggest size
            file_size = getattr(getattr(media, "photo", None), "sizes", [-1])[-1]
            file_size = getattr(file_size, "size", 0) if hasattr(file_size, "size") else 0

        elif isinstance(media, MessageMediaDocument) and hasattr(media, "document"):
            doc = media.document
            file_size = getattr(doc, "size", 0)
            mime_type = getattr(doc, "mime_type", "application/octet-stream")

            # Extract filename and attributes from document
            for attr in doc.attributes:
                if isinstance(attr, DocumentAttributeFilename):
                    filename = attr.file_name
                elif isinstance(attr, DocumentAttributeVideo):
                    is_video = True
                elif isinstance(attr, DocumentAttributeAudio):
                    is_audio = True

            if not filename:
                ext = ".bin"
                if is_video:
                    ext = ".mp4"
                elif is_audio:
                    ext = ".mp3"
                elif "image" in mime_type:
                    ext = ".jpg"
                filename = f"doc_{message.id}{ext}"

            lower_name = filename.lower()
            ext = "." + lower_name.split(".")[-1] if "." in lower_name else ""

            if ext in VIDEO_EXTENSIONS or mime_type.startswith("video/"):
                is_video = True
            elif ext in AUDIO_EXTENSIONS or mime_type.startswith("audio/"):
                is_audio = True
            elif ext in IMAGE_EXTENSIONS or mime_type.startswith("image/"):
                is_photo = True
            elif ext in ARCHIVE_EXTENSIONS:
                is_archive = True
            else:
                is_doc = True
        else:
            return False, "", 0, ""

        # Check source filter rules
        if is_video and not source_config.get("download_videos", 1):
            return False, filename, file_size, mime_type
        if is_audio and not source_config.get("download_audio", 1):
            return False, filename, file_size, mime_type
        if is_photo and not source_config.get("download_images", 0):
            return False, filename, file_size, mime_type
        if is_archive and not source_config.get("download_archives", 1):
            return False, filename, file_size, mime_type
        if is_doc and not is_video and not is_audio and not is_photo and not is_archive and not source_config.get("download_documents", 1):
            return False, filename, file_size, mime_type

        # Size thresholds
        min_size = source_config.get("min_size_bytes", 0)
        max_size = source_config.get("max_size_bytes", 0)

        if min_size and min_size > 0 and file_size < min_size:
            return False, filename, file_size, mime_type
        if max_size and max_size > 0 and file_size > max_size:
            return False, filename, file_size, mime_type

        return True, filename, file_size, mime_type


source_manager = SourceManager()
