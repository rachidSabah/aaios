"""Platform adapter base — the interface every platform implements.

The kernel never calls ``subprocess`` or ``open()`` directly — it goes
through the Gateway (L1), which in turn calls the platform adapter.

This module defines the abstract interface. Concrete implementations:
  - ``WindowsPlatform`` — Windows 11 / Server 2022 (primary target)
  - ``LinuxPlatform`` — Linux (v1.1; stubbed in v1)
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass
class ShellResult:
    """The result of a shell command execution."""

    exit_code: int
    stdout: str
    stderr: str
    duration_s: float
    command: str
    shell: str  # 'powershell' / 'pwsh' / 'bash' / 'cmd'


class PlatformAdapter(Protocol):
    """The interface every platform adapter implements."""

    @property
    def name(self) -> str:
        """Return the platform name (``windows`` / ``linux``)."""
        ...

    @property
    def is_windows(self) -> bool:
        """Return True if this is a Windows platform."""
        ...

    @property
    def is_linux(self) -> bool:
        """Return True if this is a Linux platform."""
        ...

    @property
    def home_dir(self) -> Path:
        """Return the user's home directory."""
        ...

    @property
    def config_dir(self) -> Path:
        """Return the system-wide config directory."""
        ...

    @property
    def data_dir(self) -> Path:
        """Return the system-wide data directory."""
        ...

    @property
    def cache_dir(self) -> Path:
        """Return the system-wide cache directory."""
        ...

    @property
    def log_dir(self) -> Path:
        """Return the system-wide log directory."""
        ...

    @property
    def temp_dir(self) -> Path:
        """Return the system temp directory."""
        ...

    def normalize_path(self, path: str | Path) -> Path:
        """Normalize a path to the platform's native form."""
        ...

    def is_path_safe(self, path: Path, sandbox_root: Path) -> bool:
        """Return True if ``path`` is within ``sandbox_root`` (no traversal)."""
        ...

    def default_shell(self) -> str:
        """Return the default shell executable (``pwsh`` / ``bash``)."""
        ...

    async def exec_shell(
        self,
        command: str,
        *,
        cwd: Path | None = None,
        env: dict[str, str] | None = None,
        timeout_s: float | None = None,
        shell: str | None = None,
    ) -> ShellResult:
        """Execute a shell command and return the result."""
        ...

    def supported(self) -> bool:
        """Return True if this platform is fully supported (not a stub)."""
        ...
