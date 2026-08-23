"""Service management CLI commands for Windows (Install, Start, Stop, Status, Remove)."""

import os
import sys
import subprocess
import logging
from typing import Dict, Any

from app import __service_name__, __service_display_name__

try:
    import win32serviceutil
    import win32service
    WIN32_AVAILABLE = True
except ImportError:
    WIN32_AVAILABLE = False

logger = logging.getLogger(__name__)


def is_admin() -> bool:
    """Checks if current process has Windows Administrator privileges."""
    try:
        import ctypes
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False


def get_service_status() -> Dict[str, Any]:
    """Queries Windows Service Control Manager for service status."""
    if not WIN32_AVAILABLE:
        return {"installed": False, "status": "WIN32_UNAVAILABLE", "message": "pywin32 not installed."}

    try:
        status = win32serviceutil.QueryServiceStatus(__service_name__)
        state = status[1]
        state_map = {
            win32service.SERVICE_STOPPED: "STOPPED",
            win32service.SERVICE_START_PENDING: "START_PENDING",
            win32service.SERVICE_STOP_PENDING: "STOP_PENDING",
            win32service.SERVICE_RUNNING: "RUNNING",
            win32service.SERVICE_CONTINUE_PENDING: "CONTINUE_PENDING",
            win32service.SERVICE_PAUSE_PENDING: "PAUSE_PENDING",
            win32service.SERVICE_PAUSED: "PAUSED",
        }
        return {
            "installed": True,
            "status": state_map.get(state, "UNKNOWN"),
            "raw_state": state,
        }
    except Exception as e:
        return {
            "installed": False,
            "status": "NOT_INSTALLED",
            "message": str(e),
        }


def install_service(exe_path: str = None) -> bool:
    """Installs the Telegram Downloader Windows Service."""
    if not WIN32_AVAILABLE:
        print("[!] pywin32 is not installed. Cannot register Windows service.")
        return False

    from app.service.windows_service import TelegramDownloaderWindowsService
    try:
        print(f"[*] Registering Windows Service '{__service_name_}' (Automatic startup)...")
        win32serviceutil.InstallService(
            TelegramDownloaderWindowsService,
            __service_name_,
            __service_display_name_,
            startType=win32service.SERVICE_AUTO_START,
        )
        print("[+] Service registered successfully.")
        return True
    except Exception as e:
        print(f"[-] Failed to install service: {e}")
        return False


def start_service() -> bool:
    """Starts the Windows Service."""
    if not WIN32_AVAILABLE:
        return False
    try:
        print(f"[*] Starting Windows Service '{__service_name_}'...")
        win32serviceutil.StartService(__service_name_)
        print("[+] Service start signal sent.")
        return True
    except Exception as e:
        print(f"[-] Failed to start service: {e}")
        return False


def stop_service() -> bool:
    """Stops the Windows Service."""
    if not WIN32_AVAILABLE:
        return False
    try:
        print(f"[*] Stopping Windows Service '{__service_name_}'...")
        win32serviceutil.StopService(__service_name_)
        print("[+] Service stop signal sent.")
        return True
    except Exception as e:
        print(f"[-] Failed to stop service: {e}")
        return False


def restart_service() -> bool:
    """Restarts the Windows Service."""
    if not WIN32_AVAILABLE:
        return False
    try:
        print(f"[*] Restarting Windows Service '{__service_name_}'...")
        win32serviceutil.RestartService(__service_name_)
        print("[+] Service restarted.")
        return True
    except Exception as e:
        print(f"[-] Failed to restart service: {e}")
        return False


def remove_service() -> bool:
    """Unregisters the Windows Service."""
    if not WIN32_AVAILABLE:
        return False
    try:
        print(f"[*] Removing Windows Service '{__service_name_}'...")
        win32serviceutil.RemoveService(__service_name_)
        print("[+] Service removed.")
        return True
    except Exception as e:
        print(f"[-] Failed to remove service: {e}")
        return False
