"""Desktop Surface — native desktop application entry point for AAiOS.

This module provides the Desktop Runtime bootstrapper that the native shell
(Tauri, Win32, etc.) calls to start the desktop application. It wires the
DesktopRuntimeManager, starts the API server, and opens the Mission Control UI.

Usage:
    from surfaces.desktop import boot_desktop, shutdown_desktop
    await boot_desktop()
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Any
from uuid import uuid4

from core.contracts.actor import ActorRef
from core.contracts.event import Event
from core.event_bus import get_bus, init_bus
from core.event_bus.memory import InMemoryEventStore
from core.logging import get_logger
from services.desktop.manager import DesktopRuntimeConfig, DesktopRuntimeManager

_log = get_logger(__name__)

_RUNTIME: DesktopRuntimeManager | None = None


async def boot_desktop(
    *,
    workspace_root: str | Path | None = None,
    app_version: str = "1.0.0-rc1",
    enable_system_tray: bool = True,
    enable_notifications: bool = True,
    enable_auto_update: bool = True,
    enable_offline_mode: bool = True,
    enable_local_ai: bool = True,
    enable_performance_monitor: bool = True,
    enable_crash_reporter: bool = True,
) -> DesktopRuntimeManager:
    """Boot the complete Desktop Runtime.

    Boot order:
      1. Kernel (logging, config, event bus, platform)
      2. Desktop Runtime Manager (all desktop services)
      3. API server (FastAPI)
      4. Mission Control UI (served by the API)
      5. System tray (if enabled)

    Returns the DesktopRuntimeManager instance.
    """
    global _RUNTIME

    # 1. Boot kernel if not already booted
    from core.bootstrap import boot_kernel, is_booted

    if not is_booted():
        await boot_kernel()

    # 2. Desktop Runtime Manager
    root = Path(workspace_root or Path.cwd()).resolve()
    config = DesktopRuntimeConfig(
        workspace_root=root,
        app_version=app_version,
        enable_system_tray=enable_system_tray,
        enable_notifications=enable_notifications,
        enable_auto_update=enable_auto_update,
        enable_offline_mode=enable_offline_mode,
        enable_local_ai=enable_local_ai,
        enable_performance_monitor=enable_performance_monitor,
        enable_crash_reporter=enable_crash_reporter,
    )
    runtime = DesktopRuntimeManager(config=config)

    success = await runtime.boot()
    if not success:
        _log.warning("desktop.boot.partial", errors=runtime.boot_errors)

    _RUNTIME = runtime

    # 3. Emit desktop.ready
    bus = get_bus()
    await bus.publish(
        Event(
            topic="desktop.ready",
            correlation_id=uuid4(),
            actor=ActorRef.system(),
            payload={
                "version": app_version,
                "boot_id": runtime.boot_id,
                "services": runtime.service_names(),
            },
        )
    )

    _log.info("desktop.boot.complete", version=app_version, boot_id=runtime.boot_id)
    return runtime


async def shutdown_desktop() -> None:
    """Shut down the Desktop Runtime cleanly."""
    global _RUNTIME
    if _RUNTIME is not None:
        await _RUNTIME.shutdown()
        _RUNTIME = None
    from core.bootstrap import shutdown_kernel

    await shutdown_kernel()
    _log.info("desktop.shutdown.complete")


def get_runtime() -> DesktopRuntimeManager | None:
    """Return the active DesktopRuntimeManager, or None."""
    return _RUNTIME
