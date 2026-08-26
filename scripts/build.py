"""Build script to generate standalone Windows binary using PyInstaller."""

import os
import shutil
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.resolve()


def build_standalone():
    """Runs PyInstaller to compile standalone executable."""
    dist_dir = PROJECT_ROOT / "dist"
    build_dir = PROJECT_ROOT / "build"

    print("[*] Starting PyInstaller Standalone Build...")

    # Define static files and hidden imports
    static_dir = PROJECT_ROOT / "app" / "static"
    
    cmd = [
        sys.executable,
        "-m", "PyInstaller",
        "--noconfirm",
        "--onedir",
        "--name", "TelegramDownloader",
        f"--add-data={static_dir}{os.pathsep}app/static",
        "--hidden-import=uvicorn.logging",
        "--hidden-import=uvicorn.loops",
        "--hidden-import=uvicorn.loops.auto",
        "--hidden-import=uvicorn.loops.asyncio",
        "--hidden-import=uvicorn.protocols",
        "--hidden-import=uvicorn.protocols.http",
        "--hidden-import=uvicorn.protocols.http.auto",
        "--hidden-import=uvicorn.protocols.http.h11_impl",
        "--hidden-import=uvicorn.protocols.http.httptools_impl",
        "--hidden-import=uvicorn.protocols.websockets",
        "--hidden-import=uvicorn.protocols.websockets.auto",
        "--hidden-import=uvicorn.protocols.websockets.websockets_impl",
        "--hidden-import=uvicorn.lifespans",
        "--hidden-import=uvicorn.lifespans.auto",
        "--hidden-import=uvicorn.lifespans.on",
        "--hidden-import=uvicorn.lifespans.off",
        "--hidden-import=passlib.handlers.bcrypt",
        "--hidden-import=win32timezone",
        "--hidden-import=servicemanager",
        "--hidden-import=win32service",
        "--hidden-import=win32serviceutil",
        "--hidden-import=win32event",
        "--hidden-import=cryptg",
        "--hidden-import=app.services.fast_telethon",
        "--hidden-import=argon2",
        "--hidden-import=argon2_cffi_bindings",
        "--clean",
        str(PROJECT_ROOT / "run.py"),
    ]

    print(f"[*] Command: {' '.join(cmd)}")
    res = subprocess.run(cmd, cwd=str(PROJECT_ROOT))
    if res.returncode == 0:
        print(f"[+] Build succeeded! Output at: {dist_dir / 'TelegramDownloader'}")
    else:
        print(f"[-] Build failed with exit code: {res.returncode}")
        sys.exit(res.returncode)


if __name__ == "__main__":
    build_standalone()
