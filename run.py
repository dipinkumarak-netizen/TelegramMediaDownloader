"""Universal Entrypoint for Telegram Downloader (Console, Windows Service, System Tray)."""

import argparse
import os
import sys
from pathlib import Path

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).parent.resolve()
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app import __app_name__, __version__
from app.config import settings
from app.service import service_ctl


def run_standalone():
    """Runs the FastAPI server via Uvicorn in foreground/console mode."""
    import uvicorn
    from app.main import app

    print("=" * 60)
    print(f"  {__app_name__} v{__version__} (Windows 11 Production Server)")
    print(f"  Dashboard: http://{settings.host}:{settings.port}")
    print(f"  App Data:  {settings.data_dir}")
    print("=" * 60)

    uvicorn.run(
        app,
        host=settings.host,
        port=settings.port,
        log_level=settings.log_level.lower(),
        access_log=False,
    )


def main():
    parser = argparse.ArgumentParser(description=f"{__app_name__} Server Controller")
    parser.add_argument("--host", type=str, help="Bind host address (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, help="Bind port (default: 8787)")
    parser.add_argument("--data-dir", type=str, help="Application data directory path")
    parser.add_argument("--download-dir", type=str, help="Download directory path")

    # Service Actions
    parser.add_argument("--service", action="store_true", help="Run as Windows Service (dispatched by SCM)")
    parser.add_argument("--install-service", action="store_true", help="Install Windows Service")
    parser.add_argument("--start-service", action="store_true", help="Start Windows Service")
    parser.add_argument("--stop-service", action="store_true", help="Stop Windows Service")
    parser.add_argument("--restart-service", action="store_true", help="Restart Windows Service")
    parser.add_argument("--remove-service", action="store_true", help="Remove Windows Service")
    parser.add_argument("--status-service", action="store_true", help="Query Windows Service status")
    parser.add_argument("--tray", action="store_true", help="Launch System Tray companion application")

    args = parser.parse_args()

    # Apply command-line overrides
    if args.host:
        settings.host = args.host
    if args.port:
        settings.port = args.port
    if args.data_dir:
        settings.data_dir = Path(args.data_dir).resolve()
        settings.ensure_directories()
    if args.download_dir:
        settings.download_dir = args.download_dir

    if args.install_service:
        service_ctl.install_service()
    elif args.start_service:
        service_ctl.start_service()
    elif args.stop_service:
        service_ctl.stop_service()
    elif args.restart_service:
        service_ctl.restart_service()
    elif args.remove_service:
        service_ctl.remove_service()
    elif args.status_service:
        st = service_ctl.get_service_status()
        print(f"[*] Windows Service Status: {st}")
    elif args.tray:
        from app.service.tray_app import run_tray
        run_tray()
    elif args.service:
        try:
            import win32serviceutil
            from app.service.windows_service import TelegramDownloaderWindowsService
            win32serviceutil.HandleCommandLine(TelegramDownloaderWindowsService)
        except Exception as e:
            print(f"[-] Windows Service Dispatch Error: {e}")
    else:
        run_standalone()


if __name__ == "__main__":
    main()
