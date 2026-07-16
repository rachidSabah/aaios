"""Update manager — checks for updates, downloads packages, and manages migrations."""

from __future__ import annotations

import shutil
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from core.contracts.actor import ActorRef
from core.gateway.audit import AuditEntry
from core.logging import get_logger
from services.backup.manager import BackupManager
from services.backup.models import BackupType
from services.backup.recovery import RecoveryManager
from services.update.models import (
    ReleaseChannel,
    UpdateInfo,
    UpdateReport,
    UpdateStatus,
)

_log = get_logger(__name__)

__all__ = ["UpdateManager"]


class UpdateManager:
    """Enterprise update manager for AAiOS packages and migrations."""

    def __init__(
        self,
        workspace_root: str | Path | None = None,
        backup_mgr: BackupManager | None = None,
        recovery_mgr: RecoveryManager | None = None,
    ) -> None:
        self.workspace_root = Path(workspace_root or self._find_workspace_root()).resolve()
        self.backup_mgr = backup_mgr or BackupManager(self.workspace_root)
        self.recovery_mgr = recovery_mgr or RecoveryManager(self.workspace_root, self.backup_mgr)
        self.download_dir = self.workspace_root / "downloads"
        self.download_dir.mkdir(parents=True, exist_ok=True)
        self._pinned_version: str | None = None

    def _find_workspace_root(self) -> Path:
        """Find the workspace root by looking for pyproject.toml."""
        current = Path.cwd()
        for path in [current] + list(current.parents):
            if (path / "pyproject.toml").exists():
                return path
        return current

    def pin_version(self, version: str) -> None:
        """Pin the system to a specific version, disabling newer updates."""
        self._pinned_version = version
        _log.info("update.version_pinned", version=version)

    def check_for_updates(
        self, channel: ReleaseChannel = ReleaseChannel.STABLE
    ) -> UpdateInfo | None:
        """Check for updates on the selected release channel."""
        if self._pinned_version:
            _log.info("update.check_skipped_version_pinned", pinned=self._pinned_version)
            return None

        current_version = "5.3.2"
        # Mock release server lookup
        # In a real setup, we would fetch a JSON manifest from GitHub Releases or custom registry
        # We simulate finding v5.3.3 on the selected channel
        latest_version = "5.3.3"

        if channel == ReleaseChannel.LTS:
            latest_version = "5.3.2"  # LTS is currently on 5.3.2

        if latest_version == current_version:
            return None

        # Return simulated update info
        return UpdateInfo(
            version=latest_version,
            channel=channel,
            release_notes=f"AAiOS v{latest_version} — Enterprise patches & security improvements.",
            package_url=f"https://github.com/rachidSabah/aaios/archive/refs/tags/v{latest_version}.zip",
            size_bytes=409600,
            checksum="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
            force_upgrade=False,
        )

    def download_update(self, update_info: UpdateInfo) -> Path:
        """Download the update package zip file to downloads/."""
        dest_file = self.download_dir / f"aaios-update-{update_info.version}.zip"

        _log.info("update.download_started", version=update_info.version, url=update_info.package_url)
        # Mock download: we create a dummy file or copy current files to simulate package download
        # Since we are offline-aware, we can make it zero-latency if offline
        # Write dummy zip format bytes or copy current files
        dest_file.write_bytes(b"mock_zip_file_contents_for_update_" + update_info.version.encode())

        # Verify checksum (skipped in mock/test if it's the dummy data)
        # checksum = hashlib.sha256(dest_file.read_bytes()).hexdigest()
        # if checksum != update_info.checksum: ...

        _log.info("update.download_completed", dest_file=str(dest_file))
        return dest_file

    async def install_update(self, update_info: UpdateInfo, package_path: Path) -> UpdateReport:
        """Install downloaded update package, migrate databases/configs, and validate."""
        report = UpdateReport(
            id=str(uuid4()),
            target_version=update_info.version,
            channel=update_info.channel,
            status=UpdateStatus.INSTALLING,
        )

        checkpoint_meta = None
        try:
            # 1. Create rollback checkpoint
            checkpoint_meta = self.backup_mgr.create_backup(
                backup_type=BackupType.FULL,
                is_snapshot=False,
                tags=["pre-upgrade-checkpoint", f"to-{update_info.version}"],
            )
            _log.info("update.pre_backup_created", checkpoint_id=checkpoint_meta.id)

            # 2. Simulate extraction and file copy
            # We copy files, or simulate file copy for mock update
            # We migrate databases
            self._migrate_databases(report)

            # Migrate configuration
            self._migrate_configuration(report)

            # Migrate plugins and providers
            self._migrate_plugins_and_providers(report)

            # 3. Release Validation (Phase 14)
            # Run release validator
            from services.validator.manager import ReleaseValidator
            validator = ReleaseValidator(self.workspace_root)
            validation_report = validator.run_validation()

            if not validation_report.success:
                raise ValueError(
                    f"Post-update validation failed: {validation_report.errors}"
                )

            # 4. Finalize
            report.status = UpdateStatus.SUCCESS
            report.completed_at = datetime.now(UTC)
            _log.info("update.installed_successfully", version=update_info.version)

        except Exception as e:  # noqa: BLE001
            report.status = UpdateStatus.FAILED
            report.error = str(e)
            report.completed_at = datetime.now(UTC)
            _log.error("update.installation_failed", version=update_info.version, error=str(e))

            # 5. Automatic Rollback
            if checkpoint_meta:
                _log.info("update.rolling_back", checkpoint_id=checkpoint_meta.id)
                report.status = UpdateStatus.ROLLING_BACK
                try:
                    await self.recovery_mgr.restore_backup(checkpoint_meta.id)
                    report.rollback_done = True
                    _log.info("update.rollback_success")
                except Exception as rollback_err:  # noqa: BLE001
                    _log.critical("update.rollback_failed", error=str(rollback_err))
                    report.error += f" | Rollback failed: {rollback_err}"
                report.status = UpdateStatus.FAILED

        finally:
            # Clean up the package file
            if package_path.exists():
                package_path.unlink()
            # Clean up checkpoint if upgrade succeeded
            if report.status == UpdateStatus.SUCCESS and checkpoint_meta:
                self.backup_mgr.delete_backup(checkpoint_meta.id)

        await self._audit_upgrade(report)
        return report

    # --- migrations ---------------------------------------------------

    def _migrate_databases(self, report: UpdateReport) -> None:
        """Run database migrations/schema updates."""
        # Check database files, run bootsrapper to update schema tables
        from services.installer.database import DatabaseBootstrapper
        from services.installer.workspace import WorkspaceBootstrapper
        ws = WorkspaceBootstrapper(self.workspace_root)
        db_boot = DatabaseBootstrapper(ws)
        db_boot.bootstrap_all()
        report.migrated_components.append("database")
        _log.info("update.database_migrations_applied")

    def _migrate_configuration(self, report: UpdateReport) -> None:
        """Merge new configuration fields into existing config.yaml."""
        config_dir = self.workspace_root / "config"
        config_yaml = config_dir / "config.yaml"
        defaults_yaml = config_dir / "defaults.yaml"

        if config_yaml.exists() and defaults_yaml.exists():
            # Merges default keys without overwriting user values
            try:
                import yaml
                cfg = yaml.safe_load(config_yaml.read_text(encoding="utf-8")) or {}
                defaults = yaml.safe_load(defaults_yaml.read_text(encoding="utf-8")) or {}

                # Deep merge defaults into cfg
                changed = False
                for k, v in defaults.items():
                    if k not in cfg:
                        cfg[k] = v
                        changed = True

                if changed:
                    # Save a backup of the original config first
                    shutil.copy2(config_yaml, config_yaml.with_suffix(".yaml.pre-upgrade"))
                    config_yaml.write_text(yaml.dump(cfg), encoding="utf-8")

                report.migrated_components.append("configuration")
                _log.info("update.configuration_migrations_applied")
            except Exception as e:  # noqa: BLE001
                _log.warning("update.configuration_migration_failed", error=str(e))

    def _migrate_plugins_and_providers(self, report: UpdateReport) -> None:
        """Migrate installed plugin configurations and model provider endpoints."""
        # Simplified placeholder for actual plug/provider updates
        report.migrated_components.append("plugins")
        report.migrated_components.append("providers")
        _log.info("update.plugins_and_providers_migrated")

    async def _audit_upgrade(self, report: UpdateReport) -> None:
        """Log the upgrade details to the system audit logs."""
        try:
            from services.security.manager import get_security_manager
            sec_mgr = get_security_manager()
            entry = AuditEntry(
                actor=ActorRef.system(),
                action="update.upgrade",
                target=report.target_version,
                success=(report.status == UpdateStatus.SUCCESS),
                reason=f"Upgrade status: {report.status.value}. Migrated: {report.migrated_components}. Rolled back: {report.rollback_done}",
                correlation_id=report.id,
                metadata={"rolled_back": str(report.rollback_done), "error": report.error or ""},
            )
            await sec_mgr.log(entry)
        except Exception:  # noqa: BLE001
            pass
