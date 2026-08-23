"""Storage management, Windows drive discovery, path sanitization, and atomic file operations."""

import os
import re
import shutil
import string
import sys
import uuid
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

import psutil

# Windows reserved device names (case-insensitive)
WINDOWS_RESERVED_NAMES = {
    "CON", "PRN", "AUX", "NUL",
    "COM1", "COM2", "COM3", "COM4", "COM5", "COM6", "COM7", "COM8", "COM9",
    "LPT1", "LPT2", "LPT3", "LPT4", "LPT5", "LPT6", "LPT7", "LPT8", "LPT9",
}

# Invalid characters in Windows file/directory names: < > : " / \ | ? *
ILLEGAL_CHARS_PATTERN = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def format_bytes(num_bytes: int) -> str:
    """Formats bytes to human readable format (KB, MB, GB, TB)."""
    if num_bytes < 0:
        return "0 B"
    for unit in ["B", "KB", "MB", "GB", "TB", "PB"]:
        if num_bytes < 1024.0 or unit == "PB":
            return f"{num_bytes:.2f} {unit}"
        num_bytes /= 1024.0
    return f"{num_bytes:.2f} TB"


def get_windows_drives() -> List[Dict[str, Any]]:
    """Discovers all available Windows drives with disk space and filesystem metadata."""
    drives = []
    
    # Try using psutil first
    try:
        partitions = psutil.disk_partitions(all=False)
    except Exception:
        partitions = []

    seen_mounts = set()

    for p in partitions:
        mount = p.mountpoint
        if not mount or mount in seen_mounts:
            continue
        seen_mounts.add(mount)

        drive_info: Dict[str, Any] = {
            "device": p.device,
            "mountpoint": mount,
            "fstype": p.fstype or "Unknown",
            "opts": p.opts,
            "total_bytes": 0,
            "free_bytes": 0,
            "used_bytes": 0,
            "percent_used": 0.0,
            "total_formatted": "0 B",
            "free_formatted": "0 B",
            "is_writable": False,
        }

        try:
            usage = psutil.disk_usage(mount)
            drive_info["total_bytes"] = usage.total
            drive_info["free_bytes"] = usage.free
            drive_info["used_bytes"] = usage.used
            drive_info["percent_used"] = usage.percent
            drive_info["total_formatted"] = format_bytes(usage.total)
            drive_info["free_formatted"] = format_bytes(usage.free)

            # Test write access
            test_file = Path(mount) / f".tg_write_test_{uuid.uuid4().hex[:8]}.tmp"
            try:
                test_file.write_text("test")
                if test_file.exists():
                    test_file.unlink()
                    drive_info["is_writable"] = True
            except Exception:
                drive_info["is_writable"] = False
        except Exception:
            pass

        drives.append(drive_info)

    # Fallback if psutil returned nothing (e.g. Win32 drive letters C: through Z:)
    if not drives and sys.platform == "win32":
        for letter in string.ascii_uppercase:
            drive_root = f"{letter}:\\"
            if os.path.exists(drive_root):
                try:
                    usage = shutil.disk_usage(drive_root)
                    drives.append({
                        "device": f"{letter}:",
                        "mountpoint": drive_root,
                        "fstype": "NTFS",
                        "opts": "rw",
                        "total_bytes": usage.total,
                        "free_bytes": usage.free,
                        "used_bytes": usage.used,
                        "percent_used": round((usage.used / usage.total) * 100, 1) if usage.total > 0 else 0,
                        "total_formatted": format_bytes(usage.total),
                        "free_formatted": format_bytes(usage.free),
                        "is_writable": True,
                    })
                except Exception:
                    pass

    return drives


def validate_storage_path(path_str: str) -> Tuple[bool, str]:
    """Validates if a given path is valid, can be written to, and is safe on Windows.
    
    Returns (is_valid, message).
    """
    if not path_str or not path_str.strip():
        return False, "Path cannot be empty."

    try:
        path = Path(path_str.strip()).resolve()
        
        # Check if path is on a valid Windows drive
        if sys.platform == "win32" and not path.drive:
            return False, "Path must specify a valid drive letter (e.g. C:\\... or D:\\...)."

        # Create directory if it doesn't exist
        path.mkdir(parents=True, exist_ok=True)

        if not path.is_dir():
            return False, f"Path '{path}' is not a directory."

        # Probe write access
        test_file = path / f".tg_perm_check_{uuid.uuid4().hex[:8]}.tmp"
        test_file.write_text("write_permission_probe")
        if test_file.exists():
            test_file.unlink()
            
        return True, "Path is valid and writable."
    except PermissionError:
        return False, f"Permission denied: Application cannot write to '{path_str}'."
    except Exception as e:
        return False, f"Invalid storage path: {str(e)}"


def check_free_space(directory_path: str, required_bytes: int = 0, threshold_mb: int = 1024) -> Tuple[bool, int, int]:
    """Checks if destination directory has enough free disk space.
    
    Returns (has_space, free_bytes, threshold_bytes).
    """
    try:
        path = Path(directory_path).resolve()
        if not path.exists():
            path = path.parent
        
        usage = shutil.disk_usage(str(path))
        threshold_bytes = threshold_mb * 1024 * 1024
        available_after_download = usage.free - required_bytes
        
        has_space = available_after_download >= threshold_bytes
        return has_space, usage.free, threshold_bytes
    except Exception:
        return True, 0, 0


def sanitize_filename(filename: str, max_length: int = 240) -> str:
    """Sanitizes a filename for Windows filesystem compliance.
    
    - Replaces illegal characters (< > : \" / \\ | ? *) with '_'
    - Trims leading/trailing whitespace and dots
    - Handles Windows reserved names (CON, PRN, AUX, NUL, COM1-9, LPT1-9)
    - Limits name length to avoid MAX_PATH issues while preserving extension
    """
    if not filename or not filename.strip():
        filename = f"unnamed_file_{uuid.uuid4().hex[:6]}"

    # Replace illegal characters
    cleaned = ILLEGAL_CHARS_PATTERN.sub("_", filename)
    
    # Split stem and suffix
    path_obj = Path(cleaned)
    stem = path_obj.stem.strip(" .")
    suffix = path_obj.suffix.strip(" ")
    
    if not stem:
        stem = f"file_{uuid.uuid4().hex[:6]}"

    # Check reserved DOS names
    if stem.upper() in WINDOWS_RESERVED_NAMES:
        stem = f"_{stem}"

    # Truncate if too long
    available_stem_len = max(10, max_length - len(suffix))
    if len(stem) > available_stem_len:
        stem = stem[:available_stem_len].rstrip(" .")

    sanitized = f"{stem}{suffix}" if suffix else stem
    return sanitized if sanitized else f"file_{uuid.uuid4().hex[:6]}"


def get_unique_destination_path(destination_dir: str, desired_filename: str) -> Path:
    """Generates a safe non-colliding unique filepath.
    
    Example:
    'video.mp4' -> 'video.mp4' (if not exists)
    'video.mp4' -> 'video (1).mp4' (if exists)
    'video (1).mp4' -> 'video (2).mp4' (does NOT produce 'video (1) (2).mp4')
    """
    sanitized = sanitize_filename(desired_filename)
    dest_dir = Path(destination_dir).resolve()
    dest_dir.mkdir(parents=True, exist_ok=True)
    
    target_path = dest_dir / sanitized
    if not target_path.exists():
        return target_path

    # Extract base name and counter pattern: e.g. "name (1)"
    stem = target_path.stem
    suffix = target_path.suffix
    
    # Regex to match existing counter e.g. "name (1)"
    counter_pattern = re.compile(r"^(.*?)(?:\s+\((\d+)\))?$")
    match = counter_pattern.match(stem)
    
    if match:
        base_name = match.group(1).rstrip()
        start_counter = int(match.group(2)) if match.group(2) else 1
    else:
        base_name = stem
        start_counter = 1

    counter = start_counter
    while True:
        candidate_name = f"{base_name} ({counter}){suffix}"
        candidate_path = dest_dir / candidate_name
        if not candidate_path.exists():
            return candidate_path
        counter += 1


def get_temp_download_path(final_destination_path: Path, temp_dir: Optional[Path] = None) -> Path:
    """Returns a temporary download path (.part file)."""
    if temp_dir and temp_dir.exists():
        return temp_dir / f"{final_destination_path.name}_{uuid.uuid4().hex[:6]}.part"
    return final_destination_path.with_name(f"{final_destination_path.name}.part")


def finalize_download_file(temp_path: Path, final_path: Path, expected_size: Optional[int] = None) -> Tuple[bool, str]:
    """Atomically moves temporary download file to final destination and verifies integrity.
    
    Returns (success, message).
    """
    try:
        if not temp_path.exists():
            return False, f"Temporary file '{temp_path}' not found."

        actual_size = temp_path.stat().st_size
        if expected_size is not None and expected_size > 0 and actual_size != expected_size:
            return False, f"Size mismatch: expected {expected_size} bytes, got {actual_size} bytes."

        # Ensure parent directory of final path exists
        final_path.parent.mkdir(parents=True, exist_ok=True)

        # Atomic replace on Windows/POSIX
        os.replace(str(temp_path), str(final_path))
        return True, "File finalized successfully."
    except Exception as e:
        return False, f"Failed to finalize file: {str(e)}"


def list_directory_nodes(target_path: Optional[str] = None) -> Dict[str, Any]:
    """Lists directory contents or available drives for the UI folder selector."""
    if not target_path or target_path.strip() == "":
        drives = get_windows_drives()
        return {
            "current_path": "",
            "parent_path": None,
            "drives": [
                {
                    "path": d["mountpoint"],
                    "label": f"{d['mountpoint']} ({d['free_formatted']} free / {d['total_formatted']})",
                    "free_bytes": d["free_bytes"],
                    "total_bytes": d["total_bytes"]
                }
                for d in drives
            ],
            "directories": [],
        }

    try:
        p = Path(target_path).resolve()
        if not p.exists() or not p.is_dir():
            return {"error": f"Directory '{target_path}' does not exist.", "directories": []}

        subdirs = []
        # Filter out system and hidden directories
        for entry in os.scandir(str(p)):
            try:
                if entry.is_dir(follow_symlinks=False):
                    name = entry.name
                    if name.startswith("$") or name.startswith(".") or name in [
                        "System Volume Information", "Recovery", "Windows", "PerfLogs", "AppData"
                    ]:
                        continue
                    subdirs.append({
                        "name": name,
                        "path": str(Path(entry.path).resolve()),
                    })
            except (PermissionError, OSError):
                continue

        subdirs.sort(key=lambda x: x["name"].lower())
        parent = str(p.parent.resolve()) if p.parent != p else None

        return {
            "current_path": str(p),
            "parent_path": parent,
            "directories": subdirs,
        }
    except Exception as e:
        return {"error": str(e), "directories": []}
