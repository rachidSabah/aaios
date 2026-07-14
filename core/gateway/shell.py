"""Shell gateway — the only place that runs shell commands.

This module imports ``subprocess`` directly. CI enforces that no other
module may do so (INV-02). See:
  - .github/workflows/ci.yml (architecture-invariants job)
  - tests/unit/test_phase2_structure.py::TestInvariants::test_inv_02_no_io_imports_outside_gateway
"""

from __future__ import annotations

import asyncio

# This is the SOLE import of `subprocess` in the codebase. The CI rule
# (INV-02) bans it everywhere else.
import subprocess
import time
from pathlib import Path

from core.contracts.actor import ActorRef
from core.contracts.permission import Permission
from core.gateway.audit import AuditEntry, get_audit_logger
from core.gateway.permission import get_permission_checker
from core.logging import get_logger
from core.platform import get_platform
from core.platform.base import ShellResult

_log = get_logger(__name__)


class ShellGateway:
    """Shell gateway — sandboxed, permission-checked, audit-logged."""

    DEFAULT_TIMEOUT_S: float = 30.0
    MAX_OUTPUT_BYTES: int = 8 * 1024 * 1024  # 8 MB cap per stream

    async def exec(
        self,
        command: str,
        *,
        actor: ActorRef,
        cwd: Path | None = None,
        env: dict[str, str] | None = None,
        timeout_s: float | None = None,
        sandbox_root: Path | None = None,
        shell: str | None = None,
    ) -> ShellResult:
        """Execute a shell command.

        Args:
            command: the command string (PowerShell on Windows, bash on Linux).
            actor: who is running this command.
            cwd: working directory (must be within sandbox_root if set).
            env: environment variables (merged with the parent env).
            timeout_s: max execution time (default 30s).
            sandbox_root: if set, cwd must be within this directory.
            shell: override the default shell (``pwsh`` / ``bash`` / ``cmd``).
        """
        platform = get_platform()
        if sandbox_root is not None and cwd is not None:
            cwd = platform.normalize_path(cwd)
            if not platform.is_path_safe(cwd, platform.normalize_path(sandbox_root)):
                await self._audit(actor, "gateway.shell.exec", command, False, "sandbox_violation")
                raise PermissionError(f"CWD {cwd} outside sandbox {sandbox_root}")

        checker = get_permission_checker()
        result = await checker.check(
            actor,
            Permission(name="gateway.shell.exec", resource=command[:256]),
        )
        if result.decision.value == "deny":
            await self._audit(actor, "gateway.shell.exec", command, False, "denied")
            raise PermissionError("Permission denied: shell exec")

        chosen_shell = shell or platform.default_shell()
        timeout = timeout_s or self.DEFAULT_TIMEOUT_S
        start = time.monotonic()

        try:
            exit_code, stdout, stderr = await asyncio.to_thread(
                self._exec_sync,
                command,
                chosen_shell,
                cwd,
                env,
                timeout,
            )
        except subprocess.TimeoutExpired:
            duration = time.monotonic() - start
            await self._audit(
                actor,
                "gateway.shell.exec",
                command,
                False,
                f"timeout after {timeout}s",
            )
            return ShellResult(
                exit_code=-1,
                stdout="",
                stderr=f"Timed out after {timeout}s",
                duration_s=duration,
                command=command,
                shell=chosen_shell,
            )
        except OSError as e:
            duration = time.monotonic() - start
            await self._audit(actor, "gateway.shell.exec", command, False, str(e))
            raise

        duration = time.monotonic() - start
        await self._audit(
            actor,
            "gateway.shell.exec",
            command,
            exit_code == 0,
            f"exit={exit_code} duration={duration:.2f}s",
        )
        return ShellResult(
            exit_code=exit_code,
            stdout=stdout[: self.MAX_OUTPUT_BYTES],
            stderr=stderr[: self.MAX_OUTPUT_BYTES],
            duration_s=duration,
            command=command,
            shell=chosen_shell,
        )

    def _exec_sync(
        self,
        command: str,
        shell: str,
        cwd: Path | None,
        env: dict[str, str] | None,
        timeout_s: float,
    ) -> tuple[int, str, str]:
        """Synchronous subprocess invocation (runs in a thread).

        This is the ONLY function in the codebase that calls ``subprocess.run``.
        """
        # Build the full env (parent + overrides)
        full_env = None
        if env is not None:
            import os

            full_env = dict(os.environ)
            full_env.update(env)

        # On Windows, use cmd.exe to invoke the shell so quoting is predictable.
        # On Linux, use the shell directly.
        if (
            shell.endswith("powershell.exe")
            or shell.endswith("pwsh.exe")
            or shell in ("pwsh", "powershell")
        ):
            # PowerShell: -Command "<command>"
            args = [shell, "-NoProfile", "-NonInteractive", "-Command", command]
        elif shell == "cmd.exe":
            # cmd.exe: /c "<command>"
            args = [shell, "/c", command]
        else:
            # bash/sh: -c "<command>"
            args = [shell, "-c", command]

        proc = subprocess.run(  # noqa: S603  -- intentional, INV-02
            args,
            cwd=str(cwd) if cwd else None,
            env=full_env,
            capture_output=True,
            text=True,
            timeout=timeout_s,
            check=False,  # we handle exit codes ourselves
        )
        return proc.returncode, proc.stdout or "", proc.stderr or ""

    async def _audit(
        self,
        actor: ActorRef,
        action: str,
        target: str,
        success: bool,
        reason: str,
    ) -> None:
        """Emit an audit entry."""
        logger = get_audit_logger()
        try:
            await logger.log(
                AuditEntry(
                    actor=actor,
                    action=action,
                    target=target[:512],
                    success=success,
                    reason=reason,
                ),
            )
        except Exception:
            _log.exception("gateway.audit_failed", action=action, target=target[:256])


# Singleton
_INSTANCE: ShellGateway | None = None


def get_shell_gateway() -> ShellGateway:
    """Return the singleton shell gateway."""
    global _INSTANCE
    if _INSTANCE is None:
        _INSTANCE = ShellGateway()
    return _INSTANCE
