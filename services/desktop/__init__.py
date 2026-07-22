"""Desktop Runtime — first-class platform service for native desktop operation.

The Desktop Runtime is a collection of co-operating services that together
transform AgenticOS into a production-quality native desktop application.
Every service integrates exclusively through existing public ports (Event Bus,
Platform Adapter, Gateway, Provider Framework) — no architecture bypass.

Service hierarchy:

  DesktopRuntimeManager          — lifecycle orchestrator
  ├── WindowManager              — multi-window, docking, layout
  ├── WorkspaceManager           — workspaces, projects
  ├── NativeNotificationService  — desktop notifications
  ├── SystemTray                 — system tray icon + menu
  ├── DesktopUpdater             — auto-update UI integration
  ├── OfflineRuntimeManager      — offline auth, memory, MCP, sync
  ├── LocalAIRuntimeManager      — local inference providers
  ├── DiagnosticsManager         — diagnostics, crash reporter
  ├── PerformanceMonitor         — CPU, memory, responsiveness
  ├── LocalDatabaseManager       — local SQLite/embedded database
  ├── NativeCredentialStore      — OS credential manager
  ├── DesktopPluginLoader        — hot-reload plugin loader
  └── BackgroundServiceRunner    — periodic background services
"""

from __future__ import annotations

from services.desktop.background import BackgroundServiceRunner
from services.desktop.credentials import NativeCredentialStore
from services.desktop.diagnostics import CrashReporter, DiagnosticsManager
from services.desktop.local_ai import LocalAIRuntimeManager
from services.desktop.local_db import LocalDatabaseManager
from services.desktop.manager import DesktopRuntimeConfig, DesktopRuntimeManager
from services.desktop.notifications import NativeNotificationService
from services.desktop.offline import OfflineRuntimeManager
from services.desktop.perfmon import PerformanceMonitor
from services.desktop.plugins import DesktopPluginLoader
from services.desktop.system_tray import SystemTray
from services.desktop.updater import DesktopUpdater
from services.desktop.window_manager import WindowManager, WorkspaceManager

__all__ = [
    "BackgroundServiceRunner",
    "CrashReporter",
    "DesktopPluginLoader",
    "DesktopRuntimeConfig",
    "DesktopRuntimeManager",
    "DiagnosticsManager",
    "LocalAIRuntimeManager",
    "LocalDatabaseManager",
    "NativeCredentialStore",
    "NativeNotificationService",
    "OfflineRuntimeManager",
    "PerformanceMonitor",
    "SystemTray",
    "DesktopUpdater",
    "WindowManager",
    "WorkspaceManager",
]
