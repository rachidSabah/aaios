"""Window Manager and Workspace Manager — multi-window, docking, layout persistence.

The WindowManager tracks open windows and their state (position, size, visibility).
The WorkspaceManager organizes windows into named workspaces with persistent layout.
Both are adapter abstractions so the Desktop Runtime remains platform-independent;
concrete implementations (Tauri, Win32, etc.) implement the actual window creation.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from core.logging import get_logger

_log = get_logger(__name__)


@dataclass
class WindowState:
    """Serialisable state of a single window."""
    id: str
    title: str
    url: str = ""
    x: int = 100
    y: int = 100
    width: int = 1024
    height: int = 768
    maximized: bool = False
    minimized: bool = False
    visible: bool = True
    docking_zone: str = "center"  # center, left, right, top, bottom, floating
    kind: str = "browser"  # browser, terminal, panel, dialog


@dataclass
class Workspace:
    """A named workspace with its own set of windows."""
    id: str
    name: str
    windows: list[WindowState] = field(default_factory=list)
    active: bool = False
    created_at: str = ""


class WindowManager:
    """Track window state and provide adapter-agnostic window operations."""

    def __init__(self, app_name: str = "AAiOS") -> None:
        self.app_name = app_name
        self._windows: dict[str, WindowState] = {}
        self._next_id: int = 0

    def create_window(
        self,
        title: str,
        url: str = "",
        *,
        width: int = 1024,
        height: int = 768,
        x: int | None = None,
        y: int | None = None,
        kind: str = "browser",
        docking_zone: str = "center",
    ) -> WindowState:
        wid = f"win_{self._next_id}"
        self._next_id += 1
        state = WindowState(
            id=wid,
            title=title,
            url=url,
            x=x or (100 + self._next_id * 30),
            y=y or (100 + self._next_id * 30),
            width=width,
            height=height,
            kind=kind,
            docking_zone=docking_zone,
        )
        self._windows[wid] = state
        _log.info("desktop.window.created", window_id=wid, title=title)
        return state

    def close_window(self, window_id: str) -> bool:
        win = self._windows.pop(window_id, None)
        if win:
            _log.info("desktop.window.closed", window_id=window_id)
            return True
        return False

    def get_window(self, window_id: str) -> WindowState | None:
        return self._windows.get(window_id)

    def list_windows(self) -> list[WindowState]:
        return list(self._windows.values())

    def update_window(
        self,
        window_id: str,
        *,
        x: int | None = None,
        y: int | None = None,
        width: int | None = None,
        height: int | None = None,
        maximized: bool | None = None,
        minimized: bool | None = None,
        visible: bool | None = None,
        docking_zone: str | None = None,
    ) -> WindowState | None:
        win = self._windows.get(window_id)
        if win is None:
            return None
        if x is not None: win.x = x
        if y is not None: win.y = y
        if width is not None: win.width = width
        if height is not None: win.height = height
        if maximized is not None: win.maximized = maximized
        if minimized is not None: win.minimized = minimized
        if visible is not None: win.visible = visible
        if docking_zone is not None: win.docking_zone = docking_zone
        return win

    def as_dict(self) -> dict[str, Any]:
        return {
            "app_name": self.app_name,
            "windows": [{
                "id": w.id, "title": w.title, "url": w.url,
                "x": w.x, "y": w.y, "width": w.width, "height": w.height,
                "maximized": w.maximized, "minimized": w.minimized,
                "visible": w.visible, "docking_zone": w.docking_zone, "kind": w.kind,
            } for w in self._windows.values()],
        }

    async def shutdown(self) -> None:
        self._windows.clear()
        _log.info("desktop.window_manager.shutdown")


class WorkspaceManager:
    """Manage named workspaces with persistent window layouts."""

    def __init__(
        self,
        *,
        autostart: bool = True,
        restore_state: bool = True,
        state_path: Path | None = None,
    ) -> None:
        self.autostart = autostart
        self.restore_state = restore_state
        self.state_path = state_path or Path("desktop_data") / "workspaces.json"
        self._workspaces: dict[str, Workspace] = {}
        self._current_workspace_id: str | None = None

        default_id = str(uuid4())
        self._workspaces[default_id] = Workspace(
            id=default_id, name="Default", active=True,
            created_at=datetime.now(UTC).isoformat(),
        )
        self._current_workspace_id = default_id

        if restore_state:
            self._load_state()

    def create_workspace(self, name: str) -> Workspace:
        wid = str(uuid4())
        ws = Workspace(
            id=wid, name=name, active=False,
            created_at=datetime.now(UTC).isoformat(),
        )
        self._workspaces[wid] = ws
        _log.info("desktop.workspace.created", workspace_id=wid, name=name)
        self._save_state()
        return ws

    def delete_workspace(self, workspace_id: str) -> bool:
        if workspace_id == self._current_workspace_id:
            return False  # cannot delete active workspace
        ws = self._workspaces.pop(workspace_id, None)
        if ws:
            self._save_state()
            return True
        return False

    def switch_to(self, workspace_id: str) -> Workspace | None:
        ws = self._workspaces.get(workspace_id)
        if ws is None:
            return None
        if self._current_workspace_id:
            old = self._workspaces.get(self._current_workspace_id)
            if old:
                old.active = False
        ws.active = True
        self._current_workspace_id = workspace_id
        _log.info("desktop.workspace.switched", workspace_id=workspace_id)
        self._save_state()
        return ws

    def current_workspace(self) -> Workspace | None:
        if self._current_workspace_id:
            return self._workspaces.get(self._current_workspace_id)
        return None

    def list_workspaces(self) -> list[Workspace]:
        return list(self._workspaces.values())

    def add_window_to_workspace(
        self, workspace_id: str, window: WindowState
    ) -> bool:
        ws = self._workspaces.get(workspace_id)
        if ws is None:
            return False
        ws.windows.append(window)
        self._save_state()
        return True

    def as_dict(self) -> dict[str, Any]:
        return {
            "current_workspace_id": self._current_workspace_id,
            "workspaces": [{
                "id": w.id, "name": w.name, "active": w.active,
                "windows": len(w.windows), "created_at": w.created_at,
            } for w in self._workspaces.values()],
        }

    def _save_state(self) -> None:
        if not self.restore_state:
            return
        try:
            self.state_path.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "current_workspace_id": self._current_workspace_id,
                "workspaces": {
                    wid: {
                        "id": ws.id, "name": ws.name, "active": ws.active,
                        "created_at": ws.created_at,
                        "windows": [{
                            "id": w.id, "title": w.title, "url": w.url,
                            "x": w.x, "y": w.y, "width": w.width, "height": w.height,
                            "maximized": w.maximized, "minimized": w.minimized,
                            "visible": w.visible, "docking_zone": w.docking_zone,
                            "kind": w.kind,
                        } for w in ws.windows],
                    }
                    for wid, ws in self._workspaces.items()
                },
            }
            self.state_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        except Exception as exc:  # noqa: BLE001
            _log.warning("desktop.workspace.save_failed", error=str(exc))

    def _load_state(self) -> None:
        try:
            if not self.state_path.exists():
                return
            data = json.loads(self.state_path.read_text(encoding="utf-8"))
            self._current_workspace_id = data.get("current_workspace_id")
            self._workspaces.clear()
            for wid, ws_data in data.get("workspaces", {}).items():
                windows = [
                    WindowState(**w) for w in ws_data.get("windows", [])
                ]
                self._workspaces[wid] = Workspace(
                    id=ws_data["id"], name=ws_data["name"],
                    active=ws_data.get("active", False),
                    created_at=ws_data.get("created_at", ""),
                    windows=windows,
                )
        except Exception as exc:  # noqa: BLE001
            _log.warning("desktop.workspace.load_failed", error=str(exc))

    async def shutdown(self) -> None:
        self._save_state()
        _log.info("desktop.workspace_manager.shutdown")
