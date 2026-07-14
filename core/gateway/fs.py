"""Filesystem gateway — the only place that opens files for the kernel.

All filesystem access goes through here. The gateway:
  1. Checks the path is within the caller's sandbox (no traversal).
  2. Asks the permission checker (ALLOW / DENY / ASK).
  3. Performs the operation via stdlib ``pathlib`` / ``aiofiles``.
  4. Audit-logs the call.

Phase 3 uses synchronous file I/O wrapped in ``asyncio.to_thread`` to avoid
blocking the event loop. A future optimization may use ``aiofiles`` directly.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from core.contracts.actor import ActorRef
from core.contracts.permission import Permission
from core.gateway.audit import AuditEntry, get_audit_logger
from core.gateway.permission import get_permission_checker
from core.logging import get_logger
from core.platform import get_platform

_log = get_logger(__name__)


class FileSystemGateway:
    """Filesystem gateway — sandbox-scoped, permission-checked, audit-logged."""

    async def read(
        self,
        path: Path | str,
        *,
        actor: ActorRef,
        sandbox_root: Path | None = None,
        max_bytes: int = 64 * 1024 * 1024,  # 64 MB default
    ) -> bytes:
        """Read a file. Returns the bytes.

        Args:
            path: file path.
            actor: who is reading.
            sandbox_root: if set, the path must be within this directory.
            max_bytes: read at most this many bytes (defends against huge files).
        """
        platform = get_platform()
        norm_path = platform.normalize_path(path)

        if sandbox_root is not None:
            if not platform.is_path_safe(norm_path, platform.normalize_path(sandbox_root)):
                await self._audit(
                    actor, "gateway.fs.read", str(norm_path), False, "sandbox_violation"
                )
                raise PermissionError(f"Path {norm_path} outside sandbox {sandbox_root}")

        checker = get_permission_checker()
        result = await checker.check(
            actor,
            Permission(name="gateway.fs.read", resource=str(norm_path)),
        )
        if result.decision.value == "deny":
            await self._audit(actor, "gateway.fs.read", str(norm_path), False, "denied")
            raise PermissionError(f"Permission denied: read {norm_path}")

        try:
            data = await asyncio.to_thread(self._read_sync, norm_path, max_bytes)
        except OSError as e:
            await self._audit(actor, "gateway.fs.read", str(norm_path), False, str(e))
            raise

        await self._audit(actor, "gateway.fs.read", str(norm_path), True, f"{len(data)} bytes")
        return data

    def _read_sync(self, path: Path, max_bytes: int) -> bytes:
        """Synchronous read."""
        with path.open("rb") as f:
            return f.read(max_bytes)

    async def write(
        self,
        path: Path | str,
        content: bytes | str,
        *,
        actor: ActorRef,
        sandbox_root: Path | None = None,
        append: bool = False,
    ) -> int:
        """Write a file. Returns the number of bytes written."""
        platform = get_platform()
        norm_path = platform.normalize_path(path)

        if sandbox_root is not None:
            if not platform.is_path_safe(norm_path, platform.normalize_path(sandbox_root)):
                await self._audit(
                    actor, "gateway.fs.write", str(norm_path), False, "sandbox_violation"
                )
                raise PermissionError(f"Path {norm_path} outside sandbox {sandbox_root}")

        checker = get_permission_checker()
        result = await checker.check(
            actor,
            Permission(name="gateway.fs.write", resource=str(norm_path)),
        )
        if result.decision.value == "deny":
            await self._audit(actor, "gateway.fs.write", str(norm_path), False, "denied")
            raise PermissionError(f"Permission denied: write {norm_path}")

        data = content.encode() if isinstance(content, str) else content
        mode = "ab" if append else "wb"
        try:
            await asyncio.to_thread(self._write_sync, norm_path, data, mode)
        except OSError as e:
            await self._audit(actor, "gateway.fs.write", str(norm_path), False, str(e))
            raise

        await self._audit(actor, "gateway.fs.write", str(norm_path), True, f"{len(data)} bytes")
        return len(data)

    def _write_sync(self, path: Path, data: bytes, mode: str) -> None:
        """Synchronous write."""
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open(mode) as f:
            f.write(data)

    async def list_dir(
        self,
        path: Path | str,
        *,
        actor: ActorRef,
        sandbox_root: Path | None = None,
    ) -> list[str]:
        """List directory contents. Returns the entry names."""
        platform = get_platform()
        norm_path = platform.normalize_path(path)

        if sandbox_root is not None:
            if not platform.is_path_safe(norm_path, platform.normalize_path(sandbox_root)):
                await self._audit(
                    actor, "gateway.fs.list", str(norm_path), False, "sandbox_violation"
                )
                raise PermissionError(f"Path {norm_path} outside sandbox {sandbox_root}")

        checker = get_permission_checker()
        result = await checker.check(
            actor,
            Permission(name="gateway.fs.read", resource=str(norm_path)),
        )
        if result.decision.value == "deny":
            await self._audit(actor, "gateway.fs.list", str(norm_path), False, "denied")
            raise PermissionError(f"Permission denied: list {norm_path}")

        try:
            entries = await asyncio.to_thread(lambda: [e.name for e in norm_path.iterdir()])
        except OSError as e:
            await self._audit(actor, "gateway.fs.list", str(norm_path), False, str(e))
            raise

        await self._audit(actor, "gateway.fs.list", str(norm_path), True, f"{len(entries)} entries")
        return entries

    async def delete(
        self,
        path: Path | str,
        *,
        actor: ActorRef,
        sandbox_root: Path | None = None,
    ) -> None:
        """Delete a file or empty directory."""
        platform = get_platform()
        norm_path = platform.normalize_path(path)

        if sandbox_root is not None:
            if not platform.is_path_safe(norm_path, platform.normalize_path(sandbox_root)):
                await self._audit(
                    actor, "gateway.fs.delete", str(norm_path), False, "sandbox_violation"
                )
                raise PermissionError(f"Path {norm_path} outside sandbox {sandbox_root}")

        checker = get_permission_checker()
        result = await checker.check(
            actor,
            Permission(name="gateway.fs.delete", resource=str(norm_path)),
        )
        if result.decision.value == "deny":
            await self._audit(actor, "gateway.fs.delete", str(norm_path), False, "denied")
            raise PermissionError(f"Permission denied: delete {norm_path}")

        try:
            await asyncio.to_thread(
                lambda: norm_path.unlink() if norm_path.is_file() else norm_path.rmdir()
            )
        except OSError as e:
            await self._audit(actor, "gateway.fs.delete", str(norm_path), False, str(e))
            raise

        await self._audit(actor, "gateway.fs.delete", str(norm_path), True, "ok")

    async def exists(
        self,
        path: Path | str,
        *,
        actor: ActorRef,
        sandbox_root: Path | None = None,
    ) -> bool:
        """Return True if the path exists. No audit log (read-only, cheap)."""
        platform = get_platform()
        norm_path = platform.normalize_path(path)
        if sandbox_root is not None:
            if not platform.is_path_safe(norm_path, platform.normalize_path(sandbox_root)):
                return False
        return norm_path.exists()

    async def _audit(
        self,
        actor: ActorRef,
        action: str,
        target: str,
        success: bool,
        reason: str,
    ) -> None:
        """Emit an audit entry via the audit logger."""
        logger = get_audit_logger()
        try:
            await logger.log(
                AuditEntry(
                    actor=actor,
                    action=action,
                    target=target,
                    success=success,
                    reason=reason,
                ),
            )
        except Exception:
            _log.exception("gateway.audit_failed", action=action, target=target)


# Singleton
_INSTANCE: FileSystemGateway | None = None


def get_fs_gateway() -> FileSystemGateway:
    """Return the singleton filesystem gateway."""
    global _INSTANCE
    if _INSTANCE is None:
        _INSTANCE = FileSystemGateway()
    return _INSTANCE
