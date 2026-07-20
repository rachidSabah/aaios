"""Desktop Runtime Manager — lifecycle orchestrator for all desktop services.

Boot order:
  1. DiagnosticsManager (captures startup crashes)
  2. NativeCredentialStore (needed by everything)
  3. LocalDatabaseManager (needed by offline, plugins, perfmon)
  4. WindowManager (creates the main window)
  5. WorkspaceManager (restores workspaces)
  6. SystemTray (shown after window is ready)
  7. NativeNotificationService (ready to show notifications)
  8. OfflineRuntimeManager (monitors connectivity)
  9. LocalAIRuntimeManager (starts local engines)
  10. PerformanceMonitor (starts metrics collection)
  11. DesktopPluginLoader (loads plugins)
  12. DesktopUpdater (checks for updates)
  13. BackgroundServiceRunner (starts periodic tasks)
  14. CrashReporter (armed last, catches everything)
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from core.contracts.actor import ActorRef
from core.contracts.event import Event, EventTopic
from core.event_bus import get_bus
from core.logging import get_logger
from core.platform import get_platform

_log = get_logger(__name__)


@dataclass
class DesktopRuntimeConfig:
    """Configuration for the Desktop Runtime."""
    workspace_root: str | Path = "."
    app_name: str = "AAiOS"
    app_version: str = "1.0.0-rc1"
    autostart_workspaces: bool = True
    restore_window_state: bool = True
    enable_system_tray: bool = True
    enable_notifications: bool = True
    enable_auto_update: bool = True
    enable_offline_mode: bool = True
    enable_local_ai: bool = True
    enable_performance_monitor: bool = True
    enable_crash_reporter: bool = True
    enable_plugin_loader: bool = True
    background_service_interval_s: int = 3600
    data_dir: str | None = None


class DesktopRuntimeManager:
    """Orchestrates the lifecycle of all Desktop Runtime services."""

    def __init__(self, config: DesktopRuntimeConfig | None = None) -> None:
        self.config = config or DesktopRuntimeConfig()
        self._boot_id = str(uuid4())
        self._booted = False
        self._services: dict[str, Any] = {}
        self._boot_errors: list[str] = []

    @property
    def boot_id(self) -> str:
        return self._boot_id

    @property
    def booted(self) -> bool:
        return self._booted

    @property
    def boot_errors(self) -> list[str]:
        return list(self._boot_errors)

    async def boot(self) -> bool:
        """Boot all desktop services in dependency order."""
        if self._booted:
            _log.info("desktop.already_booted", boot_id=self._boot_id)
            return True

        _log.info("desktop.booting", boot_id=self._boot_id, version=self.config.app_version)

        boot_order = [
            ("diagnostics", self._boot_diagnostics),
            ("credentials", self._boot_credentials),
            ("local_db", self._boot_local_db),
            ("window_manager", self._boot_window_manager),
            ("workspace_manager", self._boot_workspace_manager),
            ("system_tray", self._boot_system_tray),
            ("notifications", self._boot_notifications),
            ("offline", self._boot_offline),
            ("local_ai", self._boot_local_ai),
            ("perfmon", self._boot_perfmon),
            ("plugin_loader", self._boot_plugin_loader),
            ("updater", self._boot_updater),
            ("background", self._boot_background),
            ("crash_reporter", self._boot_crash_reporter),
        ]

        for name, boot_fn in boot_order:
            try:
                await boot_fn()
                _log.info("desktop.service.booted", service=name)
            except Exception as exc:  # noqa: BLE001
                _log.error("desktop.service.boot_failed", service=name, error=str(exc))
                self._boot_errors.append(f"{name}: {exc}")

        self._booted = True
        await self._emit("desktop.booted", {"boot_id": self._boot_id, "version": self.config.app_version})
        _log.info("desktop.ready", boot_id=self._boot_id, errors=len(self._boot_errors))
        return len(self._boot_errors) == 0

    async def shutdown(self) -> None:
        """Shut down all services in reverse boot order."""
        if not self._booted:
            return
        _log.info("desktop.shutting_down", boot_id=self._boot_id)
        await self._emit("desktop.shutting_down", {})

        shutdown_order = [
            "crash_reporter", "background", "updater", "plugin_loader",
            "perfmon", "local_ai", "offline", "notifications", "system_tray",
            "workspace_manager", "window_manager", "local_db", "credentials", "diagnostics",
        ]
        for name in shutdown_order:
            svc = self._services.pop(name, None)
            if svc is not None and hasattr(svc, "shutdown"):
                try:
                    await svc.shutdown()
                except Exception as exc:  # noqa: BLE001
                    _log.warning("desktop.service.shutdown_failed", service=name, error=str(exc))

        self._booted = False
        _log.info("desktop.shutdown_complete", boot_id=self._boot_id)

    # -- service accessors ------------------------------------------------

    def get(self, name: str) -> Any:
        """Get a booted service by name, or None."""
        return self._services.get(name)

    def service_names(self) -> list[str]:
        return list(self._services.keys())

    def as_dict(self) -> dict[str, Any]:
        """Serializable snapshot for diagnostics/API."""
        svcs = {}
        for name, svc in self._services.items():
            svcs[name] = getattr(svc, "as_dict", lambda: {"active": True})()
        return {
            "boot_id": self._boot_id,
            "booted": self._booted,
            "version": self.config.app_version,
            "boot_errors": self._boot_errors,
            "services": svcs,
            "uptime_s": round((datetime.now(UTC) - datetime.now(UTC)).total_seconds(), 1),
        }

    # -- boot helpers -----------------------------------------------------

    async def _boot_diagnostics(self) -> None:
        from services.desktop.diagnostics import DiagnosticsManager
        svc = DiagnosticsManager()
        self._services["diagnostics"] = svc

    async def _boot_credentials(self) -> None:
        if not self.config.enable_crash_reporter:
            from services.desktop.credentials import NativeCredentialStore
            svc = NativeCredentialStore()
            self._services["credentials"] = svc
            return
        from services.desktop.credentials import NativeCredentialStore
        svc = NativeCredentialStore()
        self._services["credentials"] = svc

    async def _boot_local_db(self) -> None:
        from services.desktop.local_db import LocalDatabaseManager
        svc = LocalDatabaseManager(
            db_dir=Path(self.config.data_dir or "desktop_data") / "db"
        )
        await svc.open()
        self._services["local_db"] = svc

    async def _boot_window_manager(self) -> None:
        from services.desktop.window_manager import WindowManager
        svc = WindowManager(app_name=self.config.app_name)
        self._services["window_manager"] = svc

    async def _boot_workspace_manager(self) -> None:
        from services.desktop.window_manager import WorkspaceManager
        svc = WorkspaceManager(
            autostart=self.config.autostart_workspaces,
            restore_state=self.config.restore_window_state,
        )
        self._services["workspace_manager"] = svc

    async def _boot_system_tray(self) -> None:
        if not self.config.enable_system_tray:
            return
        from services.desktop.system_tray import SystemTray
        svc = SystemTray(app_name=self.config.app_name)
        self._services["system_tray"] = svc

    async def _boot_notifications(self) -> None:
        if not self.config.enable_notifications:
            return
        from services.desktop.notifications import NativeNotificationService
        svc = NativeNotificationService(app_name=self.config.app_name)
        self._services["notifications"] = svc

    async def _boot_offline(self) -> None:
        if not self.config.enable_offline_mode:
            return
        from services.desktop.offline import OfflineRuntimeManager
        db = self._services.get("local_db")
        svc = OfflineRuntimeManager(db=db)
        await svc.start()
        self._services["offline"] = svc

    async def _boot_local_ai(self) -> None:
        if not self.config.enable_local_ai:
            return
        from services.desktop.local_ai import LocalAIRuntimeManager
        svc = LocalAIRuntimeManager()
        await svc.start()
        self._services["local_ai"] = svc

    async def _boot_perfmon(self) -> None:
        if not self.config.enable_performance_monitor:
            return
        from services.desktop.perfmon import PerformanceMonitor
        svc = PerformanceMonitor()
        await svc.start()
        self._services["perfmon"] = svc

    async def _boot_plugin_loader(self) -> None:
        if not self.config.enable_plugin_loader:
            return
        from services.desktop.plugins import DesktopPluginLoader
        svc = DesktopPluginLoader()
        await svc.start()
        self._services["plugin_loader"] = svc

    async def _boot_updater(self) -> None:
        if not self.config.enable_auto_update:
            return
        from services.desktop.updater import DesktopUpdater
        svc = DesktopUpdater(current_version=self.config.app_version)
        self._services["updater"] = svc

    async def _boot_background(self) -> None:
        from services.desktop.background import BackgroundServiceRunner
        svc = BackgroundServiceRunner(
            interval_s=self.config.background_service_interval_s
        )
        await svc.start()
        self._services["background"] = svc

    async def _boot_crash_reporter(self) -> None:
        if not self.config.enable_crash_reporter:
            return
        from services.desktop.diagnostics import CrashReporter
        svc = CrashReporter()
        self._services["crash_reporter"] = svc

    async def _emit(self, topic: str, payload: dict) -> None:
        try:
            bus = get_bus()
            await bus.publish(Event(
                topic=f"desktop.{topic}",
                correlation_id=uuid4(),
                actor=ActorRef.system(),
                payload=payload,
            ))
        except Exception:  # noqa: BLE001
            pass
