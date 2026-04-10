"""
vitals.py - System vitals collector.

Polls CPU, memory, and disk usage via psutil. Designed to be called from
the SSE endpoint in routes/events.py at a configurable interval.

The collector is stateless: each call returns a fresh snapshot. CPU
percent uses a small interval (0.1s) to get an instantaneous reading
without blocking the event stream.
"""

from dataclasses import dataclass
from typing import Optional

try:
    import psutil
    _HAS_PSUTIL = True
except ImportError:
    _HAS_PSUTIL = False


@dataclass
class Vitals:
    """A single point-in-time snapshot of system vitals."""
    cpu_percent: float
    mem_percent: float
    disk_percent: float
    available: bool = True


def collect_vitals() -> Vitals:
    """
    Collect a fresh snapshot of system vitals.

    Returns:
        Vitals dataclass with current values, or a zeroed snapshot
        with available=False if psutil is not installed.
    """
    if not _HAS_PSUTIL:
        return Vitals(
            cpu_percent=0.0,
            mem_percent=0.0,
            disk_percent=0.0,
            available=False,
        )

    try:
        # CPU percent with a tiny interval — non-blocking, near-instantaneous
        cpu = psutil.cpu_percent(interval=0.1)
        mem = psutil.virtual_memory().percent
        disk = psutil.disk_usage("/").percent
        return Vitals(
            cpu_percent=cpu,
            mem_percent=mem,
            disk_percent=disk,
            available=True,
        )
    except Exception:
        # Last-resort: psutil call failed for some platform-specific reason
        return Vitals(
            cpu_percent=0.0,
            mem_percent=0.0,
            disk_percent=0.0,
            available=False,
        )
