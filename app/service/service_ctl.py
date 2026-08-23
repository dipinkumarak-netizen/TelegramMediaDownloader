"""Service management CLI commands for Windows (Install, Start, Stop, Status, Remove)."""

import os
import sys
import logging
from typing import Dict, Any

from app.constants import SERVICE_NAME, SERVICE_DISPLAY_NAME, SERVICE_DESCRIPTION

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
        status = win32serviceutil.QueryServiceStatus(SERVICE_NAME)
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
        if getattr(sys, "frozen", False):
            exe_path = exe_path or sys.executable
            exe_args = "--service"
        else:
            exe_path = exe_path or sys.executable
            exe_args = f'"{os.path.abspath(sys.argv[0])}" --service'

        print(f"[*] Registering Windows Service '{SERVICE_NAME}' (Automatic startup)...")
        cls_string = win32serviceutil.GetServiceClassString(TelegramDownloaderWindowsService)
        win32serviceutil.InstallService(
            cls_string,
            SERVICE_NAME,
            SERVICE_DISPLAY_NAME,
            startType=win32service.SERVICE_AUTO_START,
            exeName=exe_path,
            exeArgs=exe_args,
            description=SERVICE_DESCRIPTION,
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
        print(f"[*] Starting Windows Service '{SERVICE_NAME}'...")
        win32serviceutil.StartService(SERVICE_NAME)
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
        print(f"[*] Stopping Windows Service '{SERVICE_NAME}'...")
        win32serviceutil.StopService(SERVICE_NAME)
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
        print(f"[*] Restarting Windows Service '{SERVICE_NAME}'...")
        win32serviceutil.RestartService(SERVICE_NAME)
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
        print(f"[*] Removing Windows Service '{SERVICE_NAME}'...")
        win32serviceutil.RemoveService(SERVICE_NAME)
        print("[+] Service removed.")
        return True
    except Exception as e:
        print(f"[-] Failed to remove service: {e}")
        return False
