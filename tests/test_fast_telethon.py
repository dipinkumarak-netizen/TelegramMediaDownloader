import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock
from telethon.tl import types

from app.services.fast_telethon import FastDownloader, fast_download


def test_fast_downloader_resolve_document():
    doc = types.Document(
        id=12345,
        access_hash=67890,
        file_reference=b"ref123",
        date=None,
        mime_type="video/mp4",
        size=1024 * 1024 * 5,  # 5 MB
        dc_id=4,
        attributes=[],
    )
    media = types.MessageMediaDocument(document=doc)
    client = MagicMock()

    downloader = FastDownloader(
        client=client,
        location=media,
        out_file="temp.mp4",
        workers=4,
    )
    downloader._resolve_location()

    assert downloader.file_size == 1024 * 1024 * 5
    assert downloader.dc_id == 4
    assert isinstance(downloader.input_location, types.InputDocumentFileLocation)
    assert downloader.input_location.id == 12345
    assert downloader.input_location.access_hash == 67890


def test_fast_downloader_resolve_photo():
    size_obj = types.PhotoSize(type="x", w=800, h=600, size=50000)
    photo = types.Photo(
        id=99999,
        access_hash=11111,
        file_reference=b"photoref",
        date=None,
        sizes=[size_obj],
        dc_id=2,
    )
    media = types.MessageMediaPhoto(photo=photo)
    client = MagicMock()

    downloader = FastDownloader(
        client=client,
        location=media,
        out_file="temp.jpg",
        workers=4,
    )
    downloader._resolve_location()

    assert downloader.file_size == 50000
    assert downloader.dc_id == 2
    assert isinstance(downloader.input_location, types.InputPhotoFileLocation)
    assert downloader.input_location.id == 99999


@pytest.mark.asyncio
async def test_fast_download_fallback(tmp_path):
    client = MagicMock()
    client.download_media = AsyncMock(return_value=str(tmp_path / "fallback.dat"))

    # Invalid location that causes fast downloader to fallback to standard download_media
    invalid_loc = "invalid_location_string"
    out_file = tmp_path / "fallback.dat"

    result = await fast_download(client, invalid_loc, out_file=out_file)

    assert client.download_media.called
    assert result == out_file
