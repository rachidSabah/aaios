"""Linux platform adapter — stubbed for v1, completed in v1.1.

Architecture is Linux-ready (this adapter exists); implementation is stubbed.
Linux is a first-class secondary target — not an afterthought — but it ships
later because the primary target is Windows 11.
"""

from __future__ import annotations

import os
from pathlib import Path

from core.logging import get_logger
from core.platform.base import ShellResult

_log = get_logger(__name__)


class LinuxPlatform:
    """Linux platform adapter — STUBBED for v1.

    All methods raise ``NotImplementedError``. The v1.1 milestone will
    complete this adapter. The architecture is already Linux-compatible;
    only the platform-specific primitives need filling in.
    """

    @property
    def name(self) -> str:
        """Return the platform name."""
        return "linux"

    @property
    def is_windows(self) -> bool:
        """Return False."""
        return False

    @property
    def is_linux(self) -> bool:
        """Return True."""
        return True

    @property
    def home_dir(self) -> Path:
        """Return the user's home directory."""
        return Path.home()

    @property
    def config_dir(self) -> Path:
        """Return the system-wide config directory (``/etc/aaios``)."""
        return Path("/etc/aaios")

    @property
    def data_dir(self) -> Path:
        """Return the system-wide data directory (``/var/lib/aaios``)."""
        return Path("/var/lib/aaios")

    @property
    def cache_dir(self) -> Path:
        """Return the system-wide cache directory (``/var/cache/aaios``)."""
        return Path("/var/cache/aaios")

    @property
    def log_dir(self) -> Path:
        """Return the system-wide log directory (``/var/log/aaios``)."""
        return Path("/var/log/aaios")

    @property
    def temp_dir(self) -> Path:
        """Return the system temp directory for AAiOS (``/tmp/aaios``).

        ``/tmp`` is the conventional Linux temp dir. The path is constructed
        from ``tempfile.gettempdir()`` so it respects the ``TMPDIR`` env var.
        """
        import tempfile

        return Path(tempfile.gettempdir()) / "aaios"  # nosec B108 — respects TMPDIR

    def normalize_path(self, path: str | Path) -> Path:
        """Normalize a path to POSIX form."""
        return Path(path).expanduser()

    def is_path_safe(self, path: Path, sandbox_root: Path) -> bool:
        """Return True if ``path`` resolves to within ``sandbox_root``."""
        try:
            resolved = path.resolve(strict=False)
            root = sandbox_root.resolve(strict=False)
            return str(resolved).startswith(str(root))
        except (OSError, ValueError):
            return False

    def default_shell(self) -> str:
        """Return the default shell (``bash``)."""
        return os.environ.get("SHELL", "/bin/bash")

    async def exec_shell(
        self,
        command: str,
        *,
        cwd: Path | None = None,
        env: dict[str, str] | None = None,
        timeout_s: float | None = None,
        shell: str | None = None,
    ) -> ShellResult:
        """Execute a shell command.

        Stubbed in v1. Use the Gateway (``core.gateway.shell``) which delegates
        to the platform adapter — the Gateway is the only place allowed to
        invoke subprocesses (INV-02).
        """
        raise NotImplementedError(
            "Linux shell execution lands in v1.1. "
            "On Linux, use the in-process Python APIs (which work today) or "
            "run AAiOS on Windows (the primary target).",
        )

    def supported(self) -> bool:
        """Return False — Linux is not yet fully supported in v1."""
        return False
