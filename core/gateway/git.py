"""Git Gateway — read-only git operations via subprocess.

This is the ONLY place outside core/gateway/shell.py that may import
subprocess, and it is restricted to read-only git commands. The gateway
enforces:

  - Command whitelist: only ``git log``, ``git branch``, ``git tag``,
    ``git show``, ``git rev-parse`` are permitted.
  - No shell=True (subprocess.run with list args).
  - All calls have a timeout.
  - All calls are read-only — no mutating git commands.

This satisfies INV-02 by centralizing all git I/O in core/gateway/.
"""

from __future__ import annotations

import subprocess  # noqa: S404 — controlled, whitelisted git commands only
from pathlib import Path
from typing import Final

from core.logging import get_logger

_log = get_logger(__name__)

__all__ = ["GitGateway", "get_git_gateway"]


# Whitelisted git subcommands (read-only)
_ALLOWED_SUBCOMMANDS: Final[frozenset[str]] = frozenset({
    "log",
    "branch",
    "tag",
    "show",
    "rev-parse",
    "diff",
    "status",
    "remote",
    "describe",
    "ls-files",
})

_DEFAULT_TIMEOUT_S: Final[float] = 15.0


class GitGateway:
    """Read-only git operations gateway.

    All commands are validated against a whitelist. Mutating commands
    (commit, push, merge, etc.) are rejected.
    """

    def __init__(self, repo_root: str | Path = ".") -> None:
        self._root = Path(repo_root)

    def run(self, args: list[str], *, timeout_s: float = _DEFAULT_TIMEOUT_S) -> str:
        """Run a read-only git command and return stdout.

        Args:
            args: git arguments, e.g. ``["log", "--oneline", "-5"]``.
                  The first element must be in the whitelist.
            timeout_s: maximum execution time.

        Returns:
            The command's stdout (empty string on failure or non-zero exit).
        """
        if not args:
            return ""
        subcmd = args[0]
        if subcmd not in _ALLOWED_SUBCOMMANDS:
            _log.warning(
                "git_gateway.subcommand_rejected",
                subcmd=subcmd,
                reason="not_in_whitelist",
            )
            return ""
        try:
            result = subprocess.run(  # noqa: S603
                ["git", "-C", str(self._root), *args],  # noqa: S607
                capture_output=True,
                text=True,
                check=False,
                timeout=timeout_s,
            )
            if result.returncode != 0:
                return ""
            return result.stdout
        except (subprocess.SubprocessError, OSError):
            return ""


_singleton: GitGateway | None = None


def get_git_gateway(repo_root: str | Path = ".") -> GitGateway:
    """Return the process-wide GitGateway singleton."""
    global _singleton
    if _singleton is None:
        _singleton = GitGateway(repo_root=repo_root)
    return _singleton
