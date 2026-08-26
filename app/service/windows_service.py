"""Native Windows Service implementation for 24/7 background execution on Windows 11."""

import os
import sys
import threading
import logging
from pathlib import Path

# Conditional win32 imports
try:
    import win32serviceutil
    import win32service
    import win32event
    import servicemanager
    import win32api
    WIN32_AVAILABLE = True
except ImportError:
    WIN32_AVAILABLE = False

from app.constants import SERVICE_NAME, SERVICE_DISPLAY_NAME, SERVICE_DESCRIPTION
from app.config import settings

logger = logging.getLogger("TelegramDownloaderService")


if WIN32_AVAILABLE:
    class TelegramDownloaderWindowsService(win32serviceutil.ServiceFramework):
        """Native Windows Background Service running FastAPI and Telegram worker."""
        _svc_name_ = SERVICE_NAME
        _svc_display_name_ = SERVICE_DISPLAY_NAME
        _svc_description_ = SERVICE_DESCRIPTION

        def __init__(self, args):
            super().__init__(args)
            self.stop_event = win32event.CreateEvent(None, 0, 0, None)
            self.server_thread = None
            self.server = None

        def SvcStop(self):
            """Called by Windows Service Control Manager to stop the service."""
            self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
            servicemanager.LogInfoMsg(f"{self._svc_display_name_} stopping...")
            if self.server:
                self.server.should_exit = True
            win32event.SetEvent(self.stop_event)

        def SvcDoRun(self):
            """Main service execution entrypoint."""
            try:
                from app.core.logger import setup_logging
                setup_logging(settings.log_level)
            except Exception:
                pass

            servicemanager.LogMsg(
                servicemanager.EVENTLOG_INFORMATION_TYPE,
                servicemanager.PYS_SERVICE_STARTED,
                (self._svc_name_, "")
            )
            logger.info(f"Windows Service {self._svc_display_name_} started.")

            # Run Uvicorn server in a separate thread
            self.server_thread = threading.Thread(target=self._run_uvicorn_server, daemon=True)
            self.server_thread.start()

            # Block until stop event is signaled by SCM
            win32event.WaitForSingleObject(self.stop_event, win32event.INFINITE)
            logger.info(f"Windows Service {self._svc_display_name_} stopped.")

        def _run_uvicorn_server(self):
            try:
                import io
                import os
                import sys

                # Fix Windows Service Null stdout/stderr
                if sys.stdout is None:
                    sys.stdout = open(os.devnull, "w", encoding="utf-8")
                if sys.stderr is None:
                    sys.stderr = open(os.devnull, "w", encoding="utf-8")

                import asyncio
                import uvicorn
                from app.main import app

                # Ensure Windows ProactorEventLoop policy for Telethon and Uvicorn
                asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

                config = uvicorn.Config(
                    app=app,
                    host=settings.host,
                    port=settings.port,
                    log_level=settings.log_level.lower(),
                    log_config=None,  # Prevent uvicorn from trying to use colourized stdout formatter
                    access_log=False,
                    loop="asyncio",
                )
                self.server = uvicorn.Server(config)
                # Avoid signal handler registration in background service thread
                self.server.install_signal_handlers = lambda: None
                logger.info(f"Windows Service listening on http://{settings.host}:{settings.port}")
                loop.run_until_complete(self.server.serve())
            except Exception as e:
                logger.critical(f"FATAL: Windows Service Uvicorn Server error: {e}", exc_info=True)
                if WIN32_AVAILABLE:
                    try:
                        servicemanager.LogErrorMsg(f"FATAL: Windows Service Uvicorn Server error: {e}")
                    except Exception:
                        pass
else:
    class TelegramDownloaderWindowsService:
        _svc_name_ = SERVICE_NAME
        _svc_display_name_ = SERVICE_DISPLAY_NAME
        _svc_description_ = SERVICE_DESCRIPTION
