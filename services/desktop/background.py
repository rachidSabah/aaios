"""Background Service Runner — periodic maintenance and health-check tasks.

Runs a configurable set of background service functions at a regular interval.
Services are registered by name and can be started/stopped independently.
The runner publishes lifecycle events on the Event Bus.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from core.contracts.actor import ActorRef
from core.contracts.event import Event
from core.event_bus import get_bus
from core.logging import get_logger

_log = get_logger(__name__)


class BackgroundServiceRunner:
    """Run registered background service functions at a regular interval."""

    def __init__(self, *, interval_s: int = 3600) -> None:
        self._interval = interval_s
        self._services: dict[str, Callable[[], Awaitable[None]]] = {}
        self._results: dict[str, dict[str, Any]] = {}
        self._task: asyncio.Task[None] | None = None
        self._stop = asyncio.Event()

    def register(
        self,
        name: str,
        func: Callable[[], Awaitable[None]],
    ) -> None:
        self._services[name] = func
        _log.info("desktop.background.service_registered", name=name)

    def unregister(self, name: str) -> bool:
        return self._services.pop(name, None) is not None

    async def start(self) -> None:
        if self._task is not None:
            return
        self._stop.clear()
        self._task = asyncio.create_task(self._run_loop())
        _log.info("desktop.background.started", interval_s=self._interval)

    async def stop(self) -> None:
        self._stop.set()
        if self._task is not None:
            await self._task
            self._task = None
        _log.info("desktop.background.stopped")

    async def run_once(self) -> dict[str, Any]:
        results: dict[str, Any] = {}
        for name, func in self._services.items():
            try:
                start = datetime.now(UTC)
                await func()
                elapsed = (datetime.now(UTC) - start).total_seconds()
                results[name] = {"status": "ok", "elapsed_s": round(elapsed, 3)}
                self._results[name] = results[name]
            except Exception as exc:  # noqa: BLE001
                results[name] = {"status": "error", "error": str(exc)}
                self._results[name] = results[name]
                _log.warning("desktop.background.service_failed", name=name, error=str(exc))
        await self._emit("desktop.background.run_complete", {
            "services": results, "count": len(results),
        })
        return results

    def last_results(self) -> dict[str, Any]:
        return dict(self._results)

    def as_dict(self) -> dict[str, Any]:
        return {
            "interval_s": self._interval,
            "registered_services": list(self._services.keys()),
            "last_results": self._results,
        }

    async def _run_loop(self) -> None:
        while not self._stop.is_set():
            await self.run_once()
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=self._interval)
            except (TimeoutError, asyncio.TimeoutError):
                continue

    async def _emit(self, topic: str, payload: dict) -> None:
        try:
            bus = get_bus()
            await bus.publish(Event(
                topic=topic,
                correlation_id=uuid4(),
                actor=ActorRef.system(),
                payload=payload,
            ))
        except Exception:  # noqa: BLE001
            pass

    async def shutdown(self) -> None:
        await self.stop()
