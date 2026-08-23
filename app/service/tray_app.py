"""Lightweight Windows System Tray Companion for Telegram Downloader."""

import os
import sys
import webbrowser
import logging
from pathlib import Path
from PIL import Image, ImageDraw

from app import __app_name__
from app.config import settings
from app.constants import LOGS_DIR
from app.service import service_ctl

logger = logging.getLogger(__name__)


def create_tray_icon_image() -> Image.Image:
    """Creates a clean procedural tray icon image (blue circle with arrow)."""
    img = Image.new("RGBA", (64, 64), color=(0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Draw rounded blue background
    draw.ellipse([4, 4, 60, 60], fill=(56, 189, 248, 255), outline=(14, 165, 233, 255), width=2)
    # Draw download arrow
    draw.rectangle([28, 16, 36, 36], fill=(15, 23, 42, 255))
    draw.polygon([(20, 36), (44, 36), (32, 48)], fill=(15, 23, 42, 255))

    return img


def run_tray():
    """Runs the system tray companion application."""
    try:
        import pystray
    except ImportError:
        print("pystray is required for the system tray application.")
        return

    def open_dashboard(icon, item):
        url = f"http://localhost:{settings.port}"
        webbrowser.open(url)

    def on_start_service(icon, item):
        service_ctl.start_service()

    def on_stop_service(icon, item):
        service_ctl.stop_service()

    def on_restart_service(icon, item):
        service_ctl.restart_service()

    def open_logs_folder(icon, item):
        LOGS_DIR.mkdir(parents=True, exist_ok=True)
        if sys.platform == "win32":
            os.startfile(str(LOGS_DIR))

    def on_exit(icon, item):
        icon.stop()

    menu = pystray.Menu(
        pystray.MenuItem("Open Dashboard", open_dashboard, default=True),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Start Service", on_start_service),
        pystray.MenuItem("Stop Service", on_stop_service),
        pystray.MenuItem("Restart Service", on_restart_service),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Open Logs Folder", open_logs_folder),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Exit Tray Companion", on_exit),
    )

    icon = pystray.Icon(
        name=__app_name__,
        icon=create_tray_icon_image(),
        title=f"{__app_name__} (Server)",
        menu=menu
    )

    print(f"[*] Starting {__app_name__} System Tray Companion...")
    icon.run()


if __name__ == "__main__":
    run_tray()
