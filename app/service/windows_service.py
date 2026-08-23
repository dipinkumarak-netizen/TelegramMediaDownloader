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

from app import __service_name__, __service_display_name__, __service_description__
from app.config import settings

logger = logging.getLogger("TelegramDownloaderService")


if WIN32_AVAILABLE:
    class TelegramDownloaderWindowsService(win32serviceutil.ServiceFramework):
        """Native Windows Background Service running FastAPI and Telegram worker."""
        _svc_name_ = __service_name_
        _svc_display_name_ = __service_display_name_
        _svc_description_ = __service_description_

        def __init__(self, args):
            super().__init__(args)
            self.stop_event = win32event.CreateEvent(None, 0, 0, None)
            self.server_thread = None
            self.server = None

        def SvcStop(self):
            """Called by Windows Service Control Manager to stop the service."""
            self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
            servicemanager.LogInfoMsg(f"{self._svc_display_name_} stopping...")
            win32event.SetEvent(self.stop_event)

            if self.server:
                self.server.should_exit = True

        def SvcDoRun(self):
            """Main service execution entrypoint."""
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
            import uvicorn
            from app.main import app

            config = uvicorn.Config(
                app=app,
                host=settings.host,
                port=settings.port,
                log_level=settings.log_level.lower(),
                access_log=False,
            )
            self.server = uvicorn.Server(config)
            self.server.run()
else:
    class TelegramDownloaderWindowsService:
        pass
