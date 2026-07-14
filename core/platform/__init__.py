"""Platform abstraction — Windows adapter (primary), Linux adapter (v1.1 stub).

The kernel uses these adapters for:
  - Path normalization (Windows backslash vs POSIX forward slash)
  - Shell execution (PowerShell vs bash)
  - Service management (Windows Services vs systemd)
  - Task scheduling (Task Scheduler vs cron/systemd timers)
  - Sandbox primitives (Job Objects + AppContainer vs seccomp + namespaces)
  - ACL management (icacls vs chmod)

``get_platform()`` returns the right adapter based on ``sys.platform``.
"""

from __future__ import annotations

from core.platform.base import PlatformAdapter, ShellResult
from core.platform.factory import get_platform, get_platform_name
from core.platform.linux import LinuxPlatform
from core.platform.windows import WindowsPlatform

__all__ = [
    "LinuxPlatform",
    "PlatformAdapter",
    "ShellResult",
    "WindowsPlatform",
    "get_platform",
    "get_platform_name",
]
