"""Platform factory — returns the right adapter based on ``sys.platform``."""

from __future__ import annotations

import sys

from core.logging import get_logger
from core.platform.base import PlatformAdapter
from core.platform.linux import LinuxPlatform
from core.platform.windows import WindowsPlatform

_log = get_logger(__name__)

_INSTANCE: PlatformAdapter | None = None


def get_platform_name() -> str:
    """Return the current platform name (``windows`` / ``linux``)."""
    return "windows" if sys.platform == "win32" else "linux"


def get_platform() -> PlatformAdapter:
    """Return the singleton PlatformAdapter for the current OS.

    On Windows: returns ``WindowsPlatform`` (fully supported).
    On Linux: returns ``LinuxPlatform`` (stubbed in v1, full support in v1.1).
    """
    global _INSTANCE
    if _INSTANCE is not None:
        return _INSTANCE

    if sys.platform == "win32":
        _INSTANCE = WindowsPlatform()
        _log.info("platform.detected", platform="windows", supported=True)
    else:
        _INSTANCE = LinuxPlatform()
        _log.info("platform.detected", platform="linux", supported=False)
    # mypy: PlatformAdapter is a Protocol; both classes satisfy it structurally.
    return _INSTANCE
