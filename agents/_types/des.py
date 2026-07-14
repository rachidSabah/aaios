"""DesktopAgent — desktop automation.

Hermes is one implementation of this type. Future implementations:
AutoHotkey-based, pywinauto-based, OS-native.

Capabilities advertised: ``desktop.ui.*``, ``desktop.input.*``,
``desktop.screen.*``, ``desktop.app.*``, ``desktop.file.*``, ``browser.*``.

Permissions: whole-desktop by default (user must opt in per-task); each
high-level action goes through the Permission Manager.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from agents._types.gen import GenericAgent


@runtime_checkable
class DesktopAgent(GenericAgent, Protocol):
    """The Desktop automation agent type."""

    async def open_app(self, name: str) -> Any:  # returns AppHandle
        """Open an application by name."""
        ...

    async def close_app(self, pid: int) -> None:
        """Close an application by PID."""
        ...

    async def click(self, x: int, y: int) -> None:
        """Click at screen coordinates."""
        ...

    async def type_text(self, text: str) -> None:
        """Type text via the keyboard."""
        ...

    async def screenshot(self) -> bytes:
        """Capture the screen. Returns PNG bytes."""
        ...

    async def ocr(self, region: tuple[int, int, int, int] | None = None) -> str:
        """OCR the screen (optionally a region). Returns extracted text."""
        ...

    async def find_element(self, selector: str) -> Any:  # returns ElementHandle
        """Find a UI element by selector (text, role, or coordinates)."""
        ...

    async def manage_file(self, op: str, path: Path, *args: Any) -> Any:
        """Perform a file management operation (open, copy, move, delete)."""
        ...
