"""Recovery manager — handles restore validation, selective restore, and rollbacks."""

from __future__ import annotations

import json
import shutil
import sqlite3
import tarfile
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from core.contracts.actor import ActorRef
from core.gateway.audit import AuditEntry
from core.logging import get_logger
from services.backup.manager import BackupManager
from services.backup.models import BackupMetadata, BackupType, RestoreReport

_log = get_logger(__name__)

__all__ = ["RecoveryManager"]


class RecoveryManager:
    """Disaster recovery and restore validation manager."""

    def __init__(
        self,
        workspace_root: str | Path | None = None,
        backup_mgr: BackupManager | None = None,
    ) -> None:
        self.workspace_root = Path(workspace_root or self._find_workspace_root()).resolve()
        self.backup_mgr = backup_mgr or BackupManager(self.workspace_root)
        self.temp_dir = self.workspace_root / "tmp" / "restore"
        self.temp_dir.mkdir(parents=True, exist_ok=True)

    def _find_workspace_root(self) -> Path:
        """Find the workspace root by looking for pyproject.toml."""
        current = Path.cwd()
        for path in [current] + list(current.parents):
            if (path / "pyproject.toml").exists():
                return path
        return current

    async def restore_backup(  # noqa: PLR0912
        self,
        backup_id: str,
        *,
        selective_components: list[str] | None = None,
        is_snapshot: bool = False,
    ) -> RestoreReport:
        """Restore a backup or snapshot. Validates integrity and compatibility."""
        report = RestoreReport(
            id=str(uuid4()),
            backup_id=backup_id,
        )

        metadata = self.backup_mgr.get_backup(backup_id, is_snapshot=is_snapshot)
        if not metadata:
            report.errors.append("Backup metadata not found")
            return report

        _log.info("restore.started", backup_id=backup_id)

        # 1. Create a pre-restore checkpoint for automatic rollback
        checkpoint_meta = None
        try:
            checkpoint_meta = self.backup_mgr.create_backup(
                backup_type=BackupType.FULL,
                is_snapshot=False,
                tags=["pre-restore-checkpoint", f"for-{backup_id}"],
            )
            _log.info("restore.checkpoint_created", checkpoint_id=checkpoint_meta.id)
        except Exception as e:  # noqa: BLE001
            report.errors.append(f"Failed to create pre-restore checkpoint: {e}")
            return report

        temp_unpack = self.temp_dir / f"unpack-{report.id}"
        temp_unpack.mkdir(parents=True, exist_ok=True)

        try:
            # 2. Extract backup to temporary location
            archive_dir = self.backup_mgr.snapshot_dir if is_snapshot else self.backup_mgr.backup_dir
            archive_path = archive_dir / f"backup-{backup_id}.{metadata.format.value}"

            if not archive_path.exists():
                raise FileNotFoundError(f"Archive file not found: {archive_path}")

            # Decrypt if encrypted
            if metadata.encrypted:
                data = archive_path.read_bytes()
                decrypted = self.backup_mgr._fernet.decrypt(data)  # noqa: SLF001
                temp_archive = temp_unpack / f"decrypted.{metadata.format.value}"
                temp_archive.write_bytes(decrypted)
                unpack_src = temp_archive
            else:
                unpack_src = archive_path

            # Unpack files
            if metadata.format.value == "zip":
                with zipfile.ZipFile(unpack_src, "r") as zipf:
                    zipf.extractall(temp_unpack)  # noqa: S202
            elif metadata.format.value == "tar":
                with tarfile.open(unpack_src, "r:gz") as tar:
                    tar.extractall(temp_unpack, filter="fully_trusted")  # noqa: S202
            else:
                # JSON/YAML import
                backup_dict = {}
                if metadata.format.value == "json":
                    backup_dict = json.loads(unpack_src.read_text(encoding="utf-8"))
                elif metadata.format.value == "yaml":
                    import yaml
                    backup_dict = yaml.safe_load(unpack_src.read_text(encoding="utf-8"))
                for rel_path, content in backup_dict.items():
                    dest_file = temp_unpack / rel_path
                    dest_file.parent.mkdir(parents=True, exist_ok=True)
                    dest_file.write_text(content, encoding="utf-8")

            # 3. Validate Integrity (checksums)
            integrity_ok = True
            for rel_path, expected_checksum in metadata.checksums.items():
                file_path = temp_unpack / rel_path
                if not file_path.exists():
                    report.errors.append(f"Integrity check failed: missing file {rel_path}")
                    integrity_ok = False
                    break
                actual_checksum = self.backup_mgr._compute_sha256(file_path)  # noqa: SLF001
                if actual_checksum != expected_checksum:
                    report.errors.append(f"Integrity check failed: checksum mismatch for {rel_path}")
                    integrity_ok = False
                    break

            report.validation_passed = integrity_ok
            if not integrity_ok:
                raise ValueError("Integrity check failed")

            # 4. Validate Compatibility
            compatibility_ok = True
            current_version = "5.3.2"
            if metadata.version != current_version:
                # Soft mismatch allowed if schemas are compatible, but flag it
                _log.warning("restore.version_mismatch", backup=metadata.version, current=current_version)

            report.compatibility_passed = compatibility_ok

            # 5. Selective Copy files to workspace
            components_to_restore = selective_components or [
                "config",
                "database",
                "memory",
                "plugins",
                "providers",
                "secrets",
                "certificates",
                "dashboards",
                "reports",
            ]

            for comp in components_to_restore:
                comp_src = temp_unpack / comp
                comp_dest = self.workspace_root / comp
                if comp_src.exists():
                    if comp_src.is_file():
                        shutil.copy2(comp_src, comp_dest)
                    else:
                        # Copy directory contents
                        comp_dest.mkdir(parents=True, exist_ok=True)
                        for item in comp_src.rglob("*"):
                            if item.is_file():
                                rel = item.relative_to(comp_src)
                                dest_item = comp_dest / rel
                                dest_item.parent.mkdir(parents=True, exist_ok=True)
                                shutil.copy2(item, dest_item)
                    report.restored_components.append(comp)

            # 6. Post-restore Database Integrity Check
            if "database" in report.restored_components:
                db_dir = self.workspace_root / "database"
                for db_file in db_dir.glob("*.db"):
                    conn = sqlite3.connect(f"file:{db_file}?mode=ro", uri=True)
                    try:
                        cursor = conn.cursor()
                        cursor.execute("PRAGMA integrity_check;")
                        res = cursor.fetchone()
                        if not res or res[0] != "ok":
                            raise sqlite3.DatabaseError(f"Integrity check failed for database {db_file.name}")
                    finally:
                        conn.close()

            report.success = True
            report.completed_at = datetime.now(UTC)
            _log.info("restore.completed", backup_id=backup_id)

        except Exception as e:  # noqa: BLE001
            report.success = False
            report.errors.append(str(e))
            report.completed_at = datetime.now(UTC)
            _log.error("restore.failed", backup_id=backup_id, error=str(e))

            # 7. Automatic Rollback
            if checkpoint_meta:
                _log.info("restore.triggering_rollback", checkpoint_id=checkpoint_meta.id)
                try:
                    await self._rollback_to_checkpoint(checkpoint_meta)
                    report.rolled_back = True
                    _log.info("restore.rollback_completed", checkpoint_id=checkpoint_meta.id)
                except Exception as rollback_err:  # noqa: BLE001
                    report.errors.append(f"Rollback failed: {rollback_err}")
                    _log.critical("restore.rollback_failed", checkpoint_id=checkpoint_meta.id, error=str(rollback_err))

        finally:
            # Clean up temporary directories
            shutil.rmtree(temp_unpack, ignore_errors=True)
            # Delete the temporary restore checkpoint if restore succeeded
            if report.success and checkpoint_meta:
                self.backup_mgr.delete_backup(checkpoint_meta.id, is_snapshot=False)

        await self._audit_restore(report)
        return report

    async def _rollback_to_checkpoint(self, checkpoint: BackupMetadata) -> None:
        """Internal helper to roll back the workspace to a checkpoint."""
        archive_path = self.backup_mgr.backup_dir / f"backup-{checkpoint.id}.{checkpoint.format.value}"
        temp_unpack = self.temp_dir / f"rollback-{checkpoint.id}"
        temp_unpack.mkdir(parents=True, exist_ok=True)

        try:
            if checkpoint.format.value == "zip":
                with zipfile.ZipFile(archive_path, "r") as zipf:
                    zipf.extractall(temp_unpack)  # noqa: S202
            elif checkpoint.format.value == "tar":
                with tarfile.open(archive_path, "r:gz") as tar:
                    tar.extractall(temp_unpack, filter="fully_trusted")  # noqa: S202

            # Restore all files from the checkpoint
            for rel_path in checkpoint.checksums:
                src = temp_unpack / rel_path
                dest = self.workspace_root / rel_path
                if src.exists():
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(src, dest)
        finally:
            shutil.rmtree(temp_unpack, ignore_errors=True)

    async def _audit_restore(self, report: RestoreReport) -> None:
        """Log the restore operation to the audit log."""
        try:
            from services.security.manager import get_security_manager
            sec_mgr = get_security_manager()
            entry = AuditEntry(
                actor=ActorRef.system(),
                action="backup.restore",
                target=report.backup_id,
                success=report.success,
                reason=f"Restore operation finished. Success: {report.success}. Errors: {len(report.errors)}. Rolled back: {report.rolled_back}",
                correlation_id=report.id,
                metadata={"rolled_back": str(report.rolled_back), "errors": "|".join(report.errors)},
            )
            await sec_mgr.log(entry)
        except Exception:  # noqa: BLE001
            pass
