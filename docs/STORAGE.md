# Storage Management & File Safety

Telegram Downloader is engineered for **unattended 24/7 server environments** where storage integrity, collision prevention, and disk-space thresholds are critical.

---

## 1. Storage Architecture

- **Application Data Isolation**: Application databases, configuration files, and Telegram sessions are stored in `%ProgramData%\TelegramDownloader\` by default.
- **Dedicated Media Directory**: Downloads are saved to your chosen destination folder (e.g. `D:\TelegramDownloads` or network storage).
- **Subfolder Organization**: You can configure per-channel subfolders (e.g. `D:\TelegramDownloads\Movies` or `D:\TelegramDownloads\Audio`).

---

## 2. File Safety Guarantees

### Atomic File Writes (.part -> Final)
1. When downloading starts, media streams into a staging file:
   ```
   D:\TelegramDownloads\movie.mkv.part
   ```
   (or `%ProgramData%\TelegramDownloader\temp\movie.mkv_<uuid>.part`).
2. When the download reaches 100%, the file size is verified against Telegram MTProto metadata.
3. The temporary file is atomically moved to the final path via `os.replace`.
4. Incomplete or broken downloads **never** overwrite existing files or appear as valid media.

### Collision Management & Deduplication
If a file with the same name already exists in the destination:
- First collision: `video.mp4` -> `video (1).mp4`
- Second collision: `video.mp4` -> `video (2).mp4`
- Note: It will **never** cascade into `video (1) (2).mp4`.

### Windows Filename Sanitization
Telegram filenames are sanitized to prevent Windows filesystem errors:
- Illegal characters `< > : " / \ | ? *` are replaced with `_`.
- Reserved DOS device names (`CON`, `PRN`, `AUX`, `NUL`, `COM1`-`COM9`, `LPT1`-`LPT9`) are escaped (e.g. `_CON.txt`).
- Trailing spaces and dots are stripped.
- Path length is bounded to avoid `MAX_PATH` limitations.

---

## 3. Disk Space Threshold Checks

Before starting any download, the application probes available free disk space on the target volume:
```
Free Disk Space >= (File Size + Free Space Threshold)
```
- Default threshold: `1024 MB` (1 GB).
- Configurable in Web Dashboard -> **Settings**.
- If space is insufficient, the download job transitions to `FAILED` with a clear message: `"Insufficient disk space"` instead of crashing or filling the disk.
