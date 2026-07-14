"""Filesystem sandbox for the Claude Code agent.

Ensures all file operations are within the project root directory.
Uses the platform adapter's path normalization and safety check.

The sandbox is enforced at the Gateway level — the agent never gets a
direct file handle. All file operations go through gateway.fs.* with
``sandbox_root`` set to the project root.
"""

from __future__ import annotations

from pathlib import Path

from core.logging import get_logger
from core.platform import get_platform

_log = get_logger(__name__)

__all__ = ["FilesystemSandbox", "SandboxViolationError"]


class SandboxViolationError(PermissionError):
    """Raised when a path is outside the sandbox."""

    def __init__(self, path: Path, sandbox_root: Path) -> None:
        super().__init__(f"Path {path} is outside sandbox {sandbox_root}")
        self.path = path
        self.sandbox_root = sandbox_root


class FilesystemSandbox:
    """Project-scoped filesystem sandbox.

    The sandbox ensures the agent can only read/write within the project
    root directory. Path traversal attacks (``../../etc/passwd``) are blocked.
    """

    def __init__(self, project_root: Path | str) -> None:
        platform = get_platform()
        self._root = platform.normalize_path(project_root).resolve(strict=False)
        _log.info("sandbox.created", root=str(self._root))

    @property
    def root(self) -> Path:
        """Return the sandbox root."""
        return self._root

    def is_safe(self, path: Path | str) -> bool:
        """Return True if ``path`` is within the sandbox."""
        platform = get_platform()
        return platform.is_path_safe(platform.normalize_path(path), self._root)

    def validate(self, path: Path | str) -> Path:
        """Validate a path. Raises SandboxViolationError if outside the sandbox.

        Returns the normalized, resolved path.
        """
        platform = get_platform()
        norm = platform.normalize_path(path).resolve(strict=False)
        if not platform.is_path_safe(norm, self._root):
            raise SandboxViolationError(norm, self._root)
        return norm

    def resolve(self, path: Path | str) -> Path:
        """Resolve a path relative to the sandbox root.

        If ``path`` is absolute, it's validated (must be within the sandbox).
        If relative, it's joined with the sandbox root.
        """
        p = Path(path)
        if p.is_absolute():
            return self.validate(p)
        return self.validate(self._root / p)

    def to_dict(self) -> dict[str, str]:
        """Serialize for logging/debugging."""
        return {"root": str(self._root)}
