"""System metrics, hardware utilization, and uptime monitoring."""

import os
import platform
import sys
import time
from typing import Dict, Any

import psutil

from app import __version__
from app.core.storage import format_bytes

_START_TIME = time.time()


def get_system_metrics(service_status: str = "Running") -> Dict[str, Any]:
    """Collects CPU, RAM, OS, uptime, and process metrics."""
    now = time.time()
    app_uptime_seconds = int(now - _START_TIME)

    # Calculate readable uptime
    days, remainder = divmod(app_uptime_seconds, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, seconds = divmod(remainder, 60)
    uptime_parts = []
    if days > 0:
        uptime_parts.append(f"{days}d")
    if hours > 0:
        uptime_parts.append(f"{hours}h")
    uptime_parts.append(f"{minutes}m")
    uptime_parts.append(f"{seconds}s")
    uptime_formatted = " ".join(uptime_parts)

    # Memory
    mem = psutil.virtual_memory()
    # CPU (interval=None for non-blocking reading)
    cpu_pct = psutil.cpu_percent(interval=None)

    # Current process stats
    try:
        proc = psutil.Process()
        proc_mem = proc.memory_info().rss
        proc_mem_formatted = format_bytes(proc_mem)
    except Exception:
        proc_mem = 0
        proc_mem_formatted = "0 B"

    return {
        "service_status": service_status,
        "uptime_seconds": app_uptime_seconds,
        "uptime_formatted": uptime_formatted,
        "cpu_percent": cpu_pct,
        "ram_percent": mem.percent,
        "ram_used_bytes": mem.used,
        "ram_total_bytes": mem.total,
        "ram_used_formatted": format_bytes(mem.used),
        "ram_total_formatted": format_bytes(mem.total),
        "process_ram_bytes": proc_mem,
        "process_ram_formatted": proc_mem_formatted,
        "app_version": __version__,
        "python_version": f"{platform.python_implementation()} {platform.python_version()}",
        "os_name": f"{platform.system()} {platform.release()} ({platform.version()})",
    }
