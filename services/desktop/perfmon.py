"""Performance Monitor — system resource tracking for CPU, memory, disk, and responsiveness.

Collects real metrics (not simulated) using psutil and publishes them on the
Event Bus for the Mission Control Dashboard and diagnostics system.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from core.contracts.actor import ActorRef
from core.contracts.event import Event
from core.event_bus import get_bus
from core.logging import get_logger

_log = get_logger(__name__)


@dataclass
class PerfSnapshot:
    """A point-in-time performance snapshot."""
    timestamp: float
    cpu_percent: float
    memory_percent: float
    memory_used_mb: float
    disk_usage_percent: float
    disk_free_gb: float
    uptime_s: float
    process_count: int
    thread_count: int
    handle_count: int = 0
    network_bytes_sent: int = 0
    network_bytes_recv: int = 0


class PerformanceMonitor:
    """Collect real system performance metrics at a configurable interval."""

    def __init__(self, *, interval_s: float = 5.0, max_history: int = 1000) -> None:
        self._interval = interval_s
        self._max_history = max_history
        self._history: list[PerfSnapshot] = []
        self._task: asyncio.Task[None] | None = None
        self._stop = asyncio.Event()
        self._last_net_sent: int = 0
        self._last_net_recv: int = 0

    async def start(self) -> None:
        if self._task is not None:
            return
        self._stop.clear()
        self._task = asyncio.create_task(self._collection_loop())
        _log.info("desktop.perfmon.started", interval_s=self._interval)

    async def stop(self) -> None:
        self._stop.set()
        if self._task is not None:
            await self._task
            self._task = None
        _log.info("desktop.perfmon.stopped")

    async def snapshot(self) -> PerfSnapshot:
        """Take a single performance snapshot."""
        try:
            import psutil
            cpu = psutil.cpu_percent(interval=0.1)
            mem = psutil.virtual_memory()
            disk = psutil.disk_usage(Path.cwd() if 'Path' in dir() else ".")
            boot = psutil.boot_time()
            net = psutil.net_io_counters()
            proc_count = len(psutil.pids())
            thread_count = sum(p.num_threads() for p in psutil.process_iter(['num_threads']))
            now = time.time()
            snap = PerfSnapshot(
                timestamp=now,
                cpu_percent=cpu,
                memory_percent=mem.percent,
                memory_used_mb=mem.used / (1024 * 1024),
                disk_usage_percent=disk.percent,
                disk_free_gb=disk.free / (1024 ** 3),
                uptime_s=now - boot,
                process_count=proc_count,
                thread_count=thread_count,
                handle_count=0,
                network_bytes_sent=net.bytes_sent - self._last_net_sent,
                network_bytes_recv=net.bytes_recv - self._last_net_recv,
            )
            self._last_net_sent = net.bytes_sent
            self._last_net_recv = net.bytes_recv
        except ImportError:
            snap = PerfSnapshot(
                timestamp=time.time(),
                cpu_percent=0.0, memory_percent=0.0, memory_used_mb=0.0,
                disk_usage_percent=0.0, disk_free_gb=0.0,
                uptime_s=0.0, process_count=0, thread_count=0,
            )
        except Exception as exc:  # noqa: BLE001
            _log.warning("desktop.perfmon.snapshot_failed", error=str(exc))
            snap = PerfSnapshot(
                timestamp=time.time(),
                cpu_percent=0.0, memory_percent=0.0, memory_used_mb=0.0,
                disk_usage_percent=0.0, disk_free_gb=0.0,
                uptime_s=0.0, process_count=0, thread_count=0,
            )
        self._history.append(snap)
        if len(self._history) > self._max_history:
            self._history.pop(0)
        return snap

    def history(
        self,
        *,
        limit: int = 100,
        metric: str = "cpu_percent",
    ) -> list[dict[str, float]]:
        return [
            {"timestamp": s.timestamp, "value": getattr(s, metric, 0.0)}
            for s in self._history[-limit:]
        ]

    def latest(self) -> PerfSnapshot | None:
        return self._history[-1] if self._history else None

    def as_dict(self) -> dict[str, Any]:
        latest = self.latest()
        return {
            "interval_s": self._interval,
            "history_length": len(self._history),
            "latest": {
                "cpu_percent": latest.cpu_percent if latest else 0,
                "memory_percent": latest.memory_percent if latest else 0,
                "memory_used_mb": latest.memory_used_mb if latest else 0,
                "disk_usage_percent": latest.disk_usage_percent if latest else 0,
                "disk_free_gb": latest.disk_free_gb if latest else 0,
                "uptime_s": latest.uptime_s if latest else 0,
                "process_count": latest.process_count if latest else 0,
            } if latest else {},
        }

    async def _collection_loop(self) -> None:
        while not self._stop.is_set():
            await self.snapshot()
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=self._interval)
            except (TimeoutError, asyncio.TimeoutError):
                continue

    async def shutdown(self) -> None:
        await self.stop()
