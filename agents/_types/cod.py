"""CodingAgent — software engineering.

Claude Code is one implementation of this type. Future implementations:
OpenHands, Cline, Roo Code, Gemini CLI, Codex CLI.

Capabilities advertised: ``code.read``, ``code.write``, ``code.refactor``,
``code.review``, ``test.run``, ``git.*``, ``shell.execute``.

Permissions: filesystem (project-scoped), shell (project-scoped), git
(project-scoped). Network denied by default.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from agents._types.gen import GenericAgent


@runtime_checkable
class CodingAgent(GenericAgent, Protocol):
    """The Coding agent type."""

    async def read_file(self, path: Path) -> str:
        """Read a file from the project sandbox."""
        ...

    async def write_file(self, path: Path, content: str) -> None:
        """Write a file to the project sandbox."""
        ...

    async def run_tests(self, scope: str | None = None) -> Any:  # returns TestResult
        """Run the project's test suite (optionally a subset)."""
        ...

    async def git(self, operation: str, args: list[str] | None = None) -> Any:  # returns GitResult
        """Perform a git operation (commit, push, branch, etc.)."""
        ...

    async def shell(self, command: str) -> Any:  # returns ShellResult
        """Execute a shell command in the project sandbox."""
        ...

    async def review(self, diff: str) -> Any:  # returns ReviewResult
        """Review a code diff and return comments + verdict."""
        ...
