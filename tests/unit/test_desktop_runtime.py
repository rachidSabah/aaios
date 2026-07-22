"""Unit + integration tests for the Desktop Runtime.
Tests real behaviour — no mocks of framework internals. Event Bus is
initialized fresh per test module so subscriptions are isolated.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from core.bootstrap import boot_kernel, is_booted, shutdown_kernel
from services.desktop.background import BackgroundServiceRunner
from services.desktop.credentials import NativeCredentialStore
from services.desktop.diagnostics import CrashReporter, DiagnosticsManager
from services.desktop.local_ai import LocalAIRuntimeManager
from services.desktop.manager import DesktopRuntimeConfig, DesktopRuntimeManager
from services.desktop.notifications import NativeNotificationService
from services.desktop.offline import OfflineRuntimeManager
from services.desktop.perfmon import PerformanceMonitor, PerfSnapshot
from services.desktop.plugins import DesktopPluginLoader
from services.desktop.system_tray import SystemTray
from services.desktop.updater import DesktopUpdater
from services.desktop.window_manager import WindowManager, WorkspaceManager

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
async def kernel():
    if not is_booted():
        await boot_kernel()
    yield
    if is_booted():
        await shutdown_kernel()


# ---------------------------------------------------------------------------
# WindowManager
# ---------------------------------------------------------------------------


def test_create_window() -> None:
    wm = WindowManager()
    win = wm.create_window("Test", url="http://localhost:3000")
    assert win.id.startswith("win_")
    assert win.title == "Test"
    assert win.url == "http://localhost:3000"
    assert win.width == 1024
    assert win.height == 768
    assert len(wm.list_windows()) == 1


def test_close_window() -> None:
    wm = WindowManager()
    w1 = wm.create_window("W1")
    wm.create_window("W2")
    assert wm.close_window(w1.id) is True
    assert wm.close_window("nonexistent") is False
    assert len(wm.list_windows()) == 1


def test_update_window() -> None:
    wm = WindowManager()
    win = wm.create_window("Test")
    updated = wm.update_window(win.id, width=800, height=600, docking_zone="left")
    assert updated is not None
    assert updated.width == 800
    assert updated.height == 600
    assert updated.docking_zone == "left"


def test_get_window() -> None:
    wm = WindowManager()
    win = wm.create_window("Test")
    assert wm.get_window(win.id) is win
    assert wm.get_window("nope") is None


# ---------------------------------------------------------------------------
# WorkspaceManager
# ---------------------------------------------------------------------------


def test_create_and_switch_workspace(tmp_path: Path) -> None:
    wsm = WorkspaceManager(state_path=tmp_path / "ws.json")
    ws = wsm.create_workspace("Dev")
    assert ws.name == "Dev"
    assert ws.active is False
    switched = wsm.switch_to(ws.id)
    assert switched is not None
    assert switched.name == "Dev"
    curr = wsm.current_workspace()
    assert curr is not None
    assert curr.name == "Dev"
    assert len(wsm.list_workspaces()) == 2  # Default + Dev


def test_delete_workspace_not_active(tmp_path: Path) -> None:
    wsm = WorkspaceManager(state_path=tmp_path / "ws2.json")
    ws = wsm.create_workspace("Temp")
    assert wsm.delete_workspace(ws.id) is True
    assert wsm.delete_workspace("nope") is False


# ---------------------------------------------------------------------------
# NotificationService
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_notify_and_history(kernel) -> None:
    svc = NativeNotificationService()
    n1 = await svc.notify("Hello", "World", level="info")
    assert n1.title == "Hello"
    assert n1.level == "info"
    await svc.notify("Warning", "Something", level="warning", category="system")
    history = svc.history()
    assert len(history) == 2
    warns = svc.history(level="warning")
    assert len(warns) == 1
    assert warns[0].title == "Warning"


@pytest.mark.asyncio
async def test_dismiss_notification(kernel) -> None:
    svc = NativeNotificationService()
    n = await svc.notify("Dismiss me", "test")
    assert await svc.dismiss(n.id) is True
    assert await svc.dismiss("nonexistent") is False


# ---------------------------------------------------------------------------
# SystemTray
# ---------------------------------------------------------------------------


def test_tray_default_menu() -> None:
    tray = SystemTray()
    assert len(tray.as_dict()["menu"]) == 7
    assert tray.as_dict()["visible"] is False


@pytest.mark.asyncio
async def test_tray_show_hide(kernel) -> None:
    tray = SystemTray()
    await tray.show()
    assert tray.as_dict()["visible"] is True
    await tray.hide()
    assert tray.as_dict()["visible"] is False


# ---------------------------------------------------------------------------
# DiagnosticsManager
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_diagnostics_run_all(kernel) -> None:
    diag = DiagnosticsManager()
    results = await diag.run_all()
    assert len(results) >= 3
    for r in results:
        assert r.status in ("pass", "fail", "warn", "error")
        assert r.name


# ---------------------------------------------------------------------------
# CrashReporter
# ---------------------------------------------------------------------------


def test_crash_report_capture(tmp_path: Path) -> None:
    cr = CrashReporter(crash_dir=tmp_path / "crashes")
    try:
        raise ValueError("test crash")
    except ValueError as exc:
        report = cr.capture(exc, component="test")
    assert report.exception_type == "ValueError"
    assert "test crash" in report.exception_message
    assert cr.get_report(report.id) is not None
    assert cr.resolve(report.id) is True
    assert len(cr.list_reports()) == 1


# ---------------------------------------------------------------------------
# PerformanceMonitor
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_perfmon_snapshot(kernel) -> None:
    pm = PerformanceMonitor()
    snap = await pm.snapshot()
    assert isinstance(snap, PerfSnapshot)
    assert snap.cpu_percent >= 0


@pytest.mark.asyncio
async def test_perfmon_history(kernel) -> None:
    pm = PerformanceMonitor()
    await pm.snapshot()
    await pm.snapshot()
    history = pm.history(metric="cpu_percent", limit=10)
    assert len(history) >= 2
    for h in history:
        assert "timestamp" in h
        assert "value" in h


# ---------------------------------------------------------------------------
# OfflineRuntimeManager
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_offline_enqueue_and_queue(kernel) -> None:
    offline = OfflineRuntimeManager()
    item_id = offline.enqueue("test_action", {"key": "value"})
    assert offline.queue_length() == 1
    items = offline.queue_items()
    assert len(items) == 1
    assert items[0].action == "test_action"
    assert items[0].id == item_id


@pytest.mark.asyncio
async def test_offline_online_property(kernel) -> None:
    offline = OfflineRuntimeManager()
    # online/offline is determined by real network probes — just check types
    assert isinstance(offline.online, bool)


# ---------------------------------------------------------------------------
# LocalAIRuntimeManager
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_local_ai_engines_listed(kernel) -> None:
    lai = LocalAIRuntimeManager()
    engines = lai.engines()
    assert len(engines) >= 3
    names = [e.name for e in engines]
    assert "ollama" in names
    assert "llama.cpp" in names


@pytest.mark.asyncio
async def test_local_ai_probe(kernel) -> None:
    lai = LocalAIRuntimeManager()
    running = await lai.probe("ollama")  # will be False if not installed
    assert isinstance(running, bool)
    assert lai.get_engine("nonexistent") is None


# ---------------------------------------------------------------------------
# DesktopPluginLoader
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_plugin_load_and_list(kernel) -> None:
    pl = DesktopPluginLoader(plugin_dir=Path("desktop_test_plugins"))
    await pl.start()
    assert len(pl.list_plugins()) == 0
    await pl.stop()


# ---------------------------------------------------------------------------
# NativeCredentialStore
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_credential_store_set_get_delete(kernel) -> None:
    store = NativeCredentialStore(data_dir=Path("desktop_test_creds"))
    assert await store.set("test_key", "test_value") is True
    val = await store.get("test_key")
    assert val == "test_value"
    assert await store.delete("test_key") is True
    assert await store.get("test_key") is None


# ---------------------------------------------------------------------------
# BackgroundServiceRunner
# ---------------------------------------------------------------------------


async def _dummy_service():
    pass


async def _failing_service():
    raise ValueError("fail")


@pytest.mark.asyncio
async def test_background_runner(kernel) -> None:
    runner = BackgroundServiceRunner(interval_s=9999)
    runner.register("dummy", _dummy_service)
    results = await runner.run_once()
    assert results["dummy"]["status"] == "ok"
    runner.register("failing", _failing_service)
    results2 = await runner.run_once()
    assert results2["failing"]["status"] == "error"


# ---------------------------------------------------------------------------
# DesktopRuntimeManager lifecycle
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_runtime_boot_and_shutdown(kernel) -> None:
    config = DesktopRuntimeConfig(
        app_version="1.0.0-test",
        enable_system_tray=False,
        enable_notifications=True,
        enable_auto_update=False,
        enable_offline_mode=True,
        enable_local_ai=True,
        enable_performance_monitor=True,
        enable_crash_reporter=True,
        enable_plugin_loader=False,
    )
    runtime = DesktopRuntimeManager(config=config)
    ok = await runtime.boot()
    assert ok
    assert runtime.booted
    assert len(runtime.service_names()) >= 5
    assert runtime.get("notifications") is not None
    assert runtime.get("offline") is not None
    assert runtime.get("perfmon") is not None
    await runtime.shutdown()
    assert not runtime.booted


# ---------------------------------------------------------------------------
# DesktopRuntimeConfig
# ---------------------------------------------------------------------------


def test_runtime_config_defaults() -> None:
    config = DesktopRuntimeConfig()
    assert config.app_name == "AAiOS"
    assert config.app_version == "1.0.0-rc1"
    assert config.enable_system_tray is True
    assert config.enable_notifications is True
    assert config.enable_offline_mode is True
    assert config.enable_local_ai is True


# ---------------------------------------------------------------------------
# DesktopUpdater
# ---------------------------------------------------------------------------


def test_updater_initialization() -> None:
    updater = DesktopUpdater(current_version="1.0.0-test")
    assert updater.current_version == "1.0.0-test"
    assert updater.channels is not None
    assert updater.manager is not None
    assert updater.service is not None
