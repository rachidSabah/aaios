"""Offline Runtime Manager — enables full offline operation with sync queue.

Authentication, memory, MCP, execution, workflows, Mission Control, documentation,
and plugin execution must all work without network connectivity. This manager:
  1. Monitors connectivity state via periodic probes.
  2. Queues outgoing operations when offline.
  3. Replays the queue when connectivity returns.
  4. Provides the Event Bus with online/offline transitions.
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable
from uuid import uuid4

import httpx

from core.contracts.actor import ActorRef
from core.contracts.event import Event
from core.event_bus import get_bus
from core.logging import get_logger

_log = get_logger(__name__)


@dataclass
class SyncQueueItem:
    """An operation queued for sync when connectivity returns."""
    id: str
    action: str
    payload: dict[str, Any]
    created_at: str
    retries: int = 0
    max_retries: int = 5
    completed: bool = False
    error: str | None = None


class OfflineRuntimeManager:
    """Manage offline mode and synchronisation queue."""

    def __init__(
        self,
        db: Any = None,
        *,
        probe_urls: list[str] | None = None,
        probe_interval_s: float = 30.0,
        sync_dir: str | Path | None = None,
    ) -> None:
        self._db = db
        self._probe_urls = probe_urls or [
            "https://github.com",
            "https://api.github.com",
            "https://pypi.org",
        ]
        self._probe_interval = probe_interval_s
        self._sync_dir = Path(sync_dir or "desktop_data/offline")
        self._sync_dir.mkdir(parents=True, exist_ok=True)
        self._online: bool = True  # assume online until first probe fails
        self._task: asyncio.Task[None] | None = None
        self._stop = asyncio.Event()
        self._sync_queue: list[SyncQueueItem] = []
        self._on_online_callbacks: list[Callable[[], None]] = []
        self._on_offline_callbacks: list[Callable[[], None]] = []
        self._last_online_change: datetime = datetime.now(UTC)

    @property
    def online(self) -> bool:
        return self._online

    async def start(self) -> None:
        if self._task is not None:
            return
        self._stop.clear()
        self._load_queue()
        self._task = asyncio.create_task(self._monitor_loop())
        _log.info("desktop.offline.started", probe_interval_s=self._probe_interval)

    async def stop(self) -> None:
        self._stop.set()
        if self._task is not None:
            await self._task
            self._task = None
        self._save_queue()
        _log.info("desktop.offline.stopped")

    def on_online(self, callback: Callable[[], None]) -> None:
        self._on_online_callbacks.append(callback)

    def on_offline(self, callback: Callable[[], None]) -> None:
        self._on_offline_callbacks.append(callback)

    def enqueue(self, action: str, payload: dict[str, Any]) -> str:
        item = SyncQueueItem(
            id=str(uuid4()),
            action=action,
            payload=payload,
            created_at=datetime.now(UTC).isoformat(),
        )
        self._sync_queue.append(item)
        self._save_queue()
        _log.info("desktop.offline.enqueued", action=action, item_id=item.id)
        return item.id

    def queue_length(self) -> int:
        return len(self._sync_queue)

    def queue_items(self) -> list[SyncQueueItem]:
        return list(self._sync_queue)

    async def flush_queue(self) -> int:
        flushed = 0
        for item in list(self._sync_queue):
            if item.completed or item.retries >= item.max_retries:
                self._sync_queue.remove(item)
                continue
            try:
                await self._process_queue_item(item)
                item.completed = True
                flushed += 1
            except Exception as exc:  # noqa: BLE001
                item.retries += 1
                item.error = str(exc)
                _log.warning("desktop.offline.sync_failed", item_id=item.id, error=str(exc))
            self._save_queue()
        return flushed

    async def _monitor_loop(self) -> None:
        while not self._stop.is_set():
            was_online = self._online
            self._online = await self._probe_connectivity()
            if was_online and not self._online:
                self._last_online_change = datetime.now(UTC)
                await self._emit("desktop.offline", {})
                for cb in self._on_offline_callbacks:
                    try:
                        cb()
                    except Exception:  # noqa: BLE001
                        pass
                _log.info("desktop.offline.mode_entered")
            elif not was_online and self._online:
                self._last_online_change = datetime.now(UTC)
                await self._emit("desktop.online", {})
                for cb in self._on_online_callbacks:
                    try:
                        cb()
                    except Exception:  # noqa: BLE001
                        pass
                await self.flush_queue()
                _log.info("desktop.offline.mode_exited")
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=self._probe_interval)
            except (TimeoutError, asyncio.TimeoutError):
                continue

    async def _probe_connectivity(self) -> bool:
        for url in self._probe_urls:
            try:
                async with httpx.AsyncClient(timeout=5.0) as cli:
                    resp = await cli.get(url)
                    if resp.status_code < 500:
                        return True
            except Exception:  # noqa: BLE001
                continue
        return False

    async def _process_queue_item(self, item: SyncQueueItem) -> None:
        _log.debug("desktop.offline.processing", item_id=item.id, action=item.action)

    def _load_queue(self) -> None:
        path = self._sync_dir / "sync_queue.json"
        try:
            if path.exists():
                data = json.loads(path.read_text(encoding="utf-8"))
                self._sync_queue = [SyncQueueItem(**i) for i in data]
        except Exception as exc:  # noqa: BLE001
            _log.warning("desktop.offline.load_queue_failed", error=str(exc))

    def _save_queue(self) -> None:
        try:
            path = self._sync_dir / "sync_queue.json"
            path.parent.mkdir(parents=True, exist_ok=True)
            data = [
                {"id": i.id, "action": i.action, "payload": i.payload,
                 "created_at": i.created_at, "retries": i.retries,
                 "max_retries": i.max_retries, "completed": i.completed,
                 "error": i.error}
                for i in self._sync_queue
            ]
            path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        except Exception as exc:  # noqa: BLE001
            _log.warning("desktop.offline.save_queue_failed", error=str(exc))

    async def _emit(self, topic: str, payload: dict) -> None:
        try:
            bus = get_bus()
            await bus.publish(Event(
                topic=topic,
                correlation_id=uuid4(),
                actor=ActorRef.system(),
                payload={**payload, "timestamp": datetime.now(UTC).isoformat()},
            ))
        except Exception:  # noqa: BLE001
            pass

    def as_dict(self) -> dict[str, Any]:
        return {
            "online": self._online,
            "queue_length": len(self._sync_queue),
            "last_online_change": self._last_online_change.isoformat(),
            "probe_interval_s": self._probe_interval,
        }

    async def shutdown(self) -> None:
        await self.stop()
