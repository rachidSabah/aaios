"""System Tray — platform-abstracted system tray icon and menu.

This service defines the interface for system tray operations. The concrete
implementation (Tauri system tray, native Win32 tray icon, etc.) is provided
by the desktop shell adapter. The service publishes tray events on the Event
Bus so other components can respond to tray interactions.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any
from uuid import uuid4

from core.contracts.actor import ActorRef
from core.contracts.event import Event
from core.event_bus import get_bus
from core.logging import get_logger

_log = get_logger(__name__)


@dataclass
class TrayMenuItem:
    """A menu item in the system tray context menu."""

    id: str
    label: str
    enabled: bool = True
    checked: bool = False
    separator: bool = False
    submenu: list[TrayMenuItem] | None = None


class SystemTray:
    """System tray icon and context menu manager."""

    def __init__(self, app_name: str = "AAiOS") -> None:
        self.app_name = app_name
        self._visible: bool = False
        self._tooltip: str = app_name
        self._icon_path: str = ""
        self._menu: list[TrayMenuItem] = self._default_menu()
        self._callbacks: dict[str, Callable[[], None]] = {}

    def _default_menu(self) -> list[TrayMenuItem]:
        return [
            TrayMenuItem(id="show", label="Show AAiOS"),
            TrayMenuItem(id="separator_1", label="", separator=True),
            TrayMenuItem(id="dashboard", label="Dashboard"),
            TrayMenuItem(id="separator_2", label="", separator=True),
            TrayMenuItem(id="updates", label="Check for Updates"),
            TrayMenuItem(id="separator_3", label="", separator=True),
            TrayMenuItem(id="quit", label="Quit"),
        ]

    async def show(self) -> None:
        self._visible = True
        await self._emit("tray.shown", {})
        _log.info("desktop.tray.shown")

    async def hide(self) -> None:
        self._visible = False
        await self._emit("tray.hidden", {})
        _log.info("desktop.tray.hidden")

    def set_tooltip(self, tooltip: str) -> None:
        self._tooltip = tooltip

    def set_icon(self, icon_path: str) -> None:
        self._icon_path = icon_path

    def set_menu(self, items: list[TrayMenuItem]) -> None:
        self._menu = items

    def on_action(self, action_id: str, callback: Callable[[], None]) -> None:
        self._callbacks[action_id] = callback

    async def handle_action(self, action_id: str) -> None:
        cb = self._callbacks.get(action_id)
        if cb:
            cb()
        await self._emit("tray.action", {"action_id": action_id})

    def as_dict(self) -> dict[str, Any]:
        return {
            "app_name": self.app_name,
            "visible": self._visible,
            "tooltip": self._tooltip,
            "menu": [
                {
                    "id": m.id,
                    "label": m.label,
                    "enabled": m.enabled,
                    "checked": m.checked,
                    "separator": m.separator,
                }
                for m in self._menu
            ],
        }

    async def _emit(self, topic: str, payload: dict) -> None:
        try:
            bus = get_bus()
            await bus.publish(
                Event(
                    topic=f"desktop.{topic}",
                    correlation_id=uuid4(),
                    actor=ActorRef.system(),
                    payload=payload,
                )
            )
        except Exception:  # noqa: BLE001
            pass

    async def shutdown(self) -> None:
        await self.hide()
        self._callbacks.clear()
        _log.info("desktop.tray.shutdown")
