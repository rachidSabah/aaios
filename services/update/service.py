"""Background update service — periodic, non-blocking update checks.

Runs on a schedule (default every 6 hours) and on an explicit "check now".
It calls :meth:`UpdateManager.check_for_updates`, and if a channel is in
``AUTO`` policy and an update is found, triggers the install. ``NOTIFY``
channels only surface availability (the UI prompts the user). ``OFF`` channels
are never touched.

The service is co-operative: it uses ``asyncio`` and can be started/stopped
cleanly. On Windows it can be backed by the Task Scheduler; on other
platforms it uses an in-process loop. Either way, the decision logic is shared.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Callable

from core.logging import get_logger
from services.update.channels import ChannelPolicy
from services.update.manager import UpdateManager
from services.update.models import ReleaseChannel, UpdateInfo

_log = get_logger(__name__)

DEFAULT_INTERVAL_S = 6 * 60 * 60  # 6 hours


class BackgroundUpdateService:
    """Scheduled, automatic update checking/installing."""

    def __init__(
        self,
        manager: UpdateManager,
        *,
        interval_s: int = DEFAULT_INTERVAL_S,
        on_update_available: Callable[[UpdateInfo], None] | None = None,
    ) -> None:
        self._mgr = manager
        self._interval = interval_s
        self._on_available = on_update_available
        self._task: asyncio.Task[None] | None = None
        self._stop = asyncio.Event()
        self.last_checked_at: datetime | None = None
        self.last_result: UpdateInfo | None = None

    @property
    def running(self) -> bool:
        """Whether the background loop is active."""
        return self._task is not None and not self._task.done()

    async def start(self) -> None:
        """Start the periodic check loop."""
        if self.running:
            return
        self._stop.clear()
        self._task = asyncio.create_task(self._loop())
        _log.info("update.service.started", interval_s=self._interval)

    async def stop(self) -> None:
        """Stop the loop and await its final iteration."""
        self._stop.set()
        if self._task is not None:
            await self._task
            self._task = None
        _log.info("update.service.stopped")

    async def check_now(self) -> UpdateInfo | None:
        """Run a single check immediately and return any available update."""
        self.last_checked_at = datetime.now(UTC)
        info = await self._mgr.check_for_updates()
        self.last_result = info
        if info is not None:
            if self._on_available:
                self._on_available(info)
            # AUTO channels install without prompting.
            if self._mgr.channels.policy_for(info.channel) == ChannelPolicy.AUTO:
                _log.info("update.service.auto_install", version=info.version)
                await self._mgr.install_update(info)
        return info

    async def _loop(self) -> None:
        """Periodic loop; resilient to individual check failures."""
        while not self._stop.is_set():
            try:
                await self.check_now()
            except Exception:  # noqa: BLE001
                _log.exception("update.service.loop_error")
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=self._interval)
            except (TimeoutError, asyncio.TimeoutError):
                continue
