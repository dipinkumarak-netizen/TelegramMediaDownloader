"""High-speed parallel multi-connection MTProto downloader for Telethon.

Enables concurrent chunk fetching across multiple DC connections to maximize
download throughput for large media files from Telegram.
"""

import asyncio
import inspect
import logging
import math
from pathlib import Path
from typing import Optional, Callable, Union, Any, List

from telethon import utils
from telethon.tl import types, functions
from telethon.tl.functions.upload import GetFileRequest

logger = logging.getLogger(__name__)

# Standard MTProto chunk size (512 KB)
CHUNK_SIZE = 512 * 1024


class FastDownloader:
    """Manages parallel worker connections and chunk distribution for a single download."""

    def __init__(
        self,
        client: Any,
        location: Any,
        out_file: Union[str, Path],
        progress_callback: Optional[Callable[[int, int], Any]] = None,
        workers: int = 4,
    ):
        self.client = client
        self.location = location
        self.out_file = Path(out_file)
        self.progress_callback = progress_callback
        self.workers_count = max(1, min(workers, 8))
        self.senders: List[Any] = []
        self.file_handle = None
        self.file_size: int = 0
        self.downloaded_bytes: int = 0
        self.lock = asyncio.Lock()
        self.dc_id: Optional[int] = None
        self.input_location: Optional[Any] = None

    def _resolve_location(self) -> None:
        """Extracts file size, DC ID, and MTProto InputFileLocation."""
        loc = self.location
        if isinstance(loc, types.Message):
            loc = loc.media

        if isinstance(loc, (types.MessageMediaDocument, types.Document)):
            doc = loc.document if isinstance(loc, types.MessageMediaDocument) else loc
            if not doc:
                raise ValueError("Message media contains no document")
            self.file_size = doc.size
            self.dc_id = doc.dc_id
            self.input_location = types.InputDocumentFileLocation(
                id=doc.id,
                access_hash=doc.access_hash,
                file_reference=doc.file_reference,
                thumb_size="",
            )
        elif isinstance(loc, (types.MessageMediaPhoto, types.Photo)):
            photo = loc.photo if isinstance(loc, types.MessageMediaPhoto) else loc
            if not photo or not photo.sizes:
                raise ValueError("Message media contains no photo sizes")
            largest = max(
                photo.sizes,
                key=lambda s: getattr(s, "size", 0)
                if hasattr(s, "size")
                else (len(s.bytes) if hasattr(s, "bytes") else 0),
            )
            self.file_size = getattr(largest, "size", 0)
            self.dc_id = photo.dc_id
            self.input_location = types.InputPhotoFileLocation(
                id=photo.id,
                access_hash=photo.access_hash,
                file_reference=photo.file_reference,
                thumb_size=largest.type,
            )
        elif hasattr(loc, "size") and hasattr(loc, "dc_id"):
            self.file_size = loc.size
            self.dc_id = loc.dc_id
            self.input_location = utils.get_input_location(loc)
        else:
            raise ValueError(f"Unsupported location object for fast download: {type(loc)}")

    async def _create_exported_sender(self) -> Optional[Any]:
        """Creates an exported MTProtoSender connected to the target DC."""
        try:
            return await self.client._create_exported_sender(self.dc_id)
        except Exception as e:
            logger.warning(f"Could not create exported sender for DC {self.dc_id}: {e}")
            return None

    async def download(self) -> Path:
        """Executes parallel chunk downloads across sender pool."""
        self._resolve_location()

        if not self.input_location or self.file_size <= 0:
            raise ValueError(f"Invalid file location or zero file size: {self.file_size}")

        total_chunks = math.ceil(self.file_size / CHUNK_SIZE)
        logger.info(
            f"FastTelethon starting: {self.file_size} bytes ({total_chunks} chunks of {CHUNK_SIZE // 1024} KB), "
            f"DC={self.dc_id}, workers={self.workers_count}"
        )

        self.out_file.parent.mkdir(parents=True, exist_ok=True)

        # Open file in read/write binary mode and preallocate
        self.file_handle = open(self.out_file, "wb+")
        try:
            self.file_handle.seek(self.file_size - 1)
            self.file_handle.write(b"\0")
            self.file_handle.flush()
        except Exception as e:
            logger.warning(f"Could not preallocate file storage: {e}")

        # Spawn pool of dedicated DC senders
        created_senders: List[Any] = []
        try:
            for _ in range(self.workers_count):
                sender = await self._create_exported_sender()
                if sender:
                    created_senders.append(sender)

            # If sender creation succeeded, use pool; otherwise fallback to client's default connection
            senders_pool = created_senders if created_senders else [None]
            queue: asyncio.Queue = asyncio.Queue()

            for idx in range(total_chunks):
                offset = idx * CHUNK_SIZE
                limit = min(CHUNK_SIZE, self.file_size - offset)
                queue.put_nowait((idx, offset, limit))

            async def worker(worker_sender: Optional[Any]) -> None:
                while not queue.empty():
                    try:
                        idx, offset, limit = queue.get_nowait()
                    except asyncio.QueueEmpty:
                        break

                    req = GetFileRequest(self.input_location, offset=offset, limit=limit)
                    chunk_bytes = None

                    for attempt in range(3):
                        try:
                            if worker_sender:
                                res = await worker_sender.send(req)
                            else:
                                res = await self.client(req)
                            chunk_bytes = res.bytes
                            break
                        except Exception as err:
                            if attempt == 2:
                                logger.error(f"Chunk #{idx} failed after 3 attempts: {err}")
                                raise err
                            await asyncio.sleep(1.0 * (attempt + 1))

                    if chunk_bytes:
                        async with self.lock:
                            self.file_handle.seek(offset)
                            self.file_handle.write(chunk_bytes)
                            self.downloaded_bytes += len(chunk_bytes)
                            current_dl = self.downloaded_bytes

                        if self.progress_callback:
                            try:
                                if inspect.iscoroutinefunction(self.progress_callback):
                                    await self.progress_callback(current_dl, self.file_size)
                                else:
                                    self.progress_callback(current_dl, self.file_size)
                            except Exception:
                                pass

                    queue.task_done()

            # Execute workers concurrently
            worker_tasks = [asyncio.create_task(worker(s)) for s in senders_pool]
            await asyncio.gather(*worker_tasks)
            self.file_handle.flush()
            return self.out_file

        finally:
            if self.file_handle:
                try:
                    self.file_handle.close()
                except Exception:
                    pass
            for s in created_senders:
                try:
                    await s.disconnect()
                except Exception:
                    pass


async def fast_download(
    client: Any,
    location: Any,
    out_file: Union[str, Path],
    progress_callback: Optional[Callable[[int, int], Any]] = None,
    workers: int = 4,
) -> Path:
    """High-level download helper with automatic fast parallel execution and fallback.

    Args:
        client: Connected Telethon TelegramClient instance.
        location: Message, MessageMediaDocument, Document, Photo, or TypeInputFileLocation.
        out_file: Target file path on disk.
        progress_callback: Optional callback receiving (downloaded_bytes, total_bytes).
        workers: Number of parallel MTProto sender connections (default: 4).

    Returns:
        Path to the downloaded file.
    """
    try:
        downloader = FastDownloader(
            client=client,
            location=location,
            out_file=out_file,
            progress_callback=progress_callback,
            workers=workers,
        )
        return await downloader.download()
    except Exception as e:
        logger.warning(
            f"Fast parallel download failed ({e}), falling back to standard Telethon download_media..."
        )
        # Fallback to standard Telethon download
        res = await client.download_media(
            location,
            file=str(out_file),
            progress_callback=progress_callback,
        )
        return Path(res)
