"""Desktop Updater — connects the Update Framework to the Desktop Runtime UI.

This service bridges the provider-based Update Framework
(:class:`~services.update.manager.UpdateManager`) with the Desktop Runtime's
notification and system-tray systems. It:
  1. Registers the :class:`~services.update.github_provider.GitHubReleaseProvider`
     with the UpdateManager.
  2. Exposes check/install/rollback workflows as async methods the Mission
     Control UI can call.
  3. Publishes ``desktop.update.*`` events on the Event Bus so the dashboard
     and system tray stay in sync.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from core.contracts.actor import ActorRef
from core.contracts.event import Event
from core.event_bus import get_bus
from core.logging import get_logger
from services.update.channels import ReleaseChannelManager
from services.update.github_provider import GitHubReleaseProvider
from services.update.manager import UpdateManager
from services.update.models import ReleaseChannel, UpdateInfo, UpdateStatus
from services.update.rollback import RollbackManager
from services.update.service import BackgroundUpdateService
from services.update.verify import PackageVerifier

_log = get_logger(__name__)


class DesktopUpdater:
    """Desktop-aware wrapper around the Update Framework."""

    def __init__(
        self,
        *,
        current_version: str = "1.0.0-rc1",
        workspace_root: str | Path | None = None,
        github_token: str | None = None,
        github_repo: str = "rachidSabah/aaios",
    ) -> None:
        self.current_version = current_version
        root = Path(workspace_root or Path.cwd()).resolve()
        self._channels = ReleaseChannelManager()
        self._rollback = RollbackManager(root)
        self._verifier = PackageVerifier()
        self._manager = UpdateManager(
            workspace_root=root,
            current_version=current_version,
            channels=self._channels,
            rollback=self._rollback,
            verifier=self._verifier,
        )
        self._provider = GitHubReleaseProvider(
            repo=github_repo,
            token=github_token,
        )
        self._manager.register_provider(self._provider)
        self._service = BackgroundUpdateService(
            self._manager,
            on_update_available=self._on_update_available,
        )
        self._last_check_result: UpdateInfo | None = None

    @property
    def manager(self) -> UpdateManager:
        return self._manager

    @property
    def channels(self) -> ReleaseChannelManager:
        return self._channels

    @property
    def service(self) -> BackgroundUpdateService:
        return self._service

    async def check(self) -> UpdateInfo | None:
        self._last_check_result = await self._manager.check_for_updates()
        await self._emit("desktop.update.check_complete", {
            "available": self._last_check_result is not None,
            "version": self._last_check_result.version if self._last_check_result else None,
        })
        return self._last_check_result

    async def install(self, info: UpdateInfo | None = None) -> Any:
        target = info or self._last_check_result
        if target is None:
            return None
        await self._emit("desktop.update.installing", {"version": target.version})
        report = await self._manager.install_update(target)
        await self._emit("desktop.update.install_complete", {
            "version": target.version,
            "status": report.status.value,
            "error": report.error,
        })
        return report

    def _on_update_available(self, info: UpdateInfo) -> None:
        try:
            bus = get_bus()
            asyncio = __import__("asyncio")
            asyncio.ensure_future(bus.publish(Event(
                topic="desktop.update.available",
                correlation_id=uuid4(),
                actor=ActorRef.system(),
                payload={
                    "version": info.version,
                    "channel": info.channel.value,
                    "release_notes": info.release_notes,
                    "size_bytes": info.size_bytes,
                },
            )))
        except Exception:  # noqa: BLE001
            pass

    def as_dict(self) -> dict[str, Any]:
        return {
            "current_version": self.current_version,
            "provider": self._provider.name,
            "channels": self._channels.as_dict(),
            "last_check_result": {
                "version": self._last_check_result.version,
                "channel": self._last_check_result.channel.value,
            } if self._last_check_result else None,
        }

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
        await self._service.stop()
        _log.info("desktop.updater.shutdown")
