"""Windows platform adapter — the primary target.

Uses:
  - PowerShell 7+ (``pwsh``) as the default shell; cmd.exe fallback
  - %ProgramData%\\AAiOS for system-wide config/data
  - %APPDATA%\\AAiOS for per-user data
  - Path normalization: backslashes, drive letters, long-path prefix
  - Sandbox check: resolve real path, ensure within sandbox root
"""

from __future__ import annotations

import os
from pathlib import Path

from core.logging import get_logger
from core.platform.base import ShellResult

_log = get_logger(__name__)


class WindowsPlatform:
    """Windows 11 / Server 2022 platform adapter (primary target)."""

    @property
    def name(self) -> str:
        """Return the platform name."""
        return "windows"

    @property
    def is_windows(self) -> bool:
        """Return True."""
        return True

    @property
    def is_linux(self) -> bool:
        """Return False."""
        return False

    @property
    def home_dir(self) -> Path:
        """Return the user's home directory (``%USERPROFILE%``)."""
        return Path(os.environ.get("USERPROFILE", str(Path.home())))

    @property
    def config_dir(self) -> Path:
        """Return the system-wide config directory (``%ProgramData%\\AAiOS\\config``)."""
        return Path(os.environ.get("ProgramData", r"C:\ProgramData")) / "AAiOS" / "config"

    @property
    def data_dir(self) -> Path:
        """Return the system-wide data directory (``%ProgramData%\\AAiOS\\data``)."""
        return Path(os.environ.get("ProgramData", r"C:\ProgramData")) / "AAiOS" / "data"

    @property
    def cache_dir(self) -> Path:
        """Return the system-wide cache directory."""
        return Path(os.environ.get("ProgramData", r"C:\ProgramData")) / "AAiOS" / "cache"

    @property
    def log_dir(self) -> Path:
        """Return the system-wide log directory."""
        return Path(os.environ.get("ProgramData", r"C:\ProgramData")) / "AAiOS" / "logs"

    @property
    def temp_dir(self) -> Path:
        """Return the system temp directory for AAiOS (``%TEMP%\\AAiOS``)."""
        return (
            Path(os.environ.get("TEMP", str(Path.home() / "AppData" / "Local" / "Temp"))) / "AAiOS"
        )

    def normalize_path(self, path: str | Path) -> Path:
        """Normalize a path to Windows form.

        - Converts forward slashes to backslashes
        - Expands ``~`` to the home directory
        - Expands environment variables
        - Adds the ``\\\\?\\`` prefix for long paths (>260 chars)
        """
        if isinstance(path, str):
            path = path.replace("/", "\\")
        p = Path(path).expanduser()
        # Expand environment variables like %ProgramData%
        if isinstance(path, str) and "%" in path:
            expanded = os.path.expandvars(path)
            p = Path(expanded)
        p_str = str(p)
        # Long path prefix
        if len(p_str) > 260 and not p_str.startswith("\\\\?\\"):
            p_str = "\\\\?\\" + p_str
        return Path(p_str)

    def is_path_safe(self, path: Path, sandbox_root: Path) -> bool:
        """Return True if ``path`` resolves to within ``sandbox_root``.

        Resolves symlinks and ``..`` traversals before checking.
        """
        try:
            resolved = path.resolve(strict=False)
            root = sandbox_root.resolve(strict=False)
            return str(resolved).lower().startswith(str(root).lower())
        except (OSError, ValueError):
            return False

    def default_shell(self) -> str:
        """Return the default shell (PowerShell 7 if present, else cmd.exe)."""
        # Check for pwsh (PowerShell 7+) on PATH
        for exe in ("pwsh.exe", "pwsh"):
            if self._which(exe):
                return exe
        # Fall back to Windows PowerShell
        ps_path = (
            Path(os.environ.get("WINDIR", r"C:\Windows"))
            / "System32"
            / "WindowsPowerShell"
            / "v1.0"
            / "powershell.exe"
        )
        if ps_path.is_file():
            return str(ps_path)
        return "cmd.exe"

    def _which(self, exe: str) -> str | None:
        """Return the full path to ``exe`` on PATH, or None."""
        for directory in os.environ.get("PATH", "").split(os.pathsep):
            full = Path(directory) / exe
            if full.is_file():
                return str(full)
        return None

    async def exec_shell(
        self,
        command: str,
        *,
        cwd: Path | None = None,
        env: dict[str, str] | None = None,
        timeout_s: float | None = None,
        shell: str | None = None,
    ) -> ShellResult:
        """Execute a PowerShell command.

        Phase 3 stub: this lives here for API completeness. The actual
        subprocess invocation goes through the Gateway (``core.gateway.shell``),
        which delegates to this method. The Gateway enforces INV-02.
        """
        # This is intentionally a thin wrapper — the Gateway does the actual
        # subprocess.Popen call (the ONLY place in the codebase that does).
        # We reach it via gateway.shell.exec(), which calls us.
        raise NotImplementedError(
            "Use core.gateway.shell.exec() — the Gateway is the only place "
            "that may invoke subprocesses directly (INV-02).",
        )

    def supported(self) -> bool:
        """Return True — Windows is fully supported in v1."""
        return True
