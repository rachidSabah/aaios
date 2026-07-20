"""Rollback manager — wraps the existing backup/recovery ports.

The framework does NOT implement its own backup format. It delegates to the
real :class:`~services.backup.manager.BackupManager` and
:class:`~services.backup.recovery.RecoveryManager` that the rest of AAiOS
already uses, so a failed update restores the exact same artifacts a manual
backup would. This keeps the architecture honest: one backup system, many
callers.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from core.logging import get_logger
from services.backup.manager import BackupManager, BackupType
from services.backup.recovery import RecoveryManager
from services.update.models import UpdateReport, UpdateStatus

_log = get_logger(__name__)


class RollbackError(RuntimeError):
    """Raised when a rollback attempt itself fails."""


class RollbackManager:
    """Create pre-update checkpoints and restore them on failure."""

    def __init__(
        self,
        workspace_root: str | Path,
        backup_mgr: BackupManager | None = None,
        recovery_mgr: RecoveryManager | None = None,
    ) -> None:
        root = Path(workspace_root).resolve()
        self.backup_mgr = backup_mgr or BackupManager(root)
        self.recovery_mgr = recovery_mgr or RecoveryManager(root, self.backup_mgr)

    def checkpoint(self, *, target_version: str) -> str:
        """Create a pre-upgrade checkpoint. Returns the backup id."""
        meta = self.backup_mgr.create_backup(
            backup_type=BackupType.FULL,
            is_snapshot=False,
            tags=["pre-upgrade-checkpoint", f"to-{target_version}"],
        )
        _log.info("update.checkpoint.created", backup_id=meta.id)
        return meta.id

    async def rollback(self, backup_id: str, *, report: UpdateReport | None = None) -> bool:
        """Restore the checkpoint. Updates ``report`` status if provided."""
        if report is not None:
            report.status = UpdateStatus.ROLLING_BACK
        try:
            restore_report = await self.recovery_mgr.restore_backup(backup_id)
        except Exception as exc:  # noqa: BLE001
            _log.critical("update.rollback.failed", error=str(exc))
            if report is not None:
                report.status = UpdateStatus.FAILED
                report.error = f"rollback failed: {exc}"
            raise RollbackError(str(exc)) from exc

        if report is not None:
            report.rollback_done = restore_report.success
            if not restore_report.success:
                report.status = UpdateStatus.FAILED
                report.error = "rollback failed: " + "; ".join(restore_report.errors)
        _log.info("update.rollback.done", success=restore_report.success)
        return restore_report.success

    def release_checkpoint(self, backup_id: str) -> None:
        """Delete a checkpoint after a successful upgrade (no longer needed)."""
        try:
            self.backup_mgr.delete_backup(backup_id)
            _log.info("update.checkpoint.released", backup_id=backup_id)
        except Exception as exc:  # noqa: BLE001
            _log.warning("update.checkpoint.release_failed", error=str(exc))
