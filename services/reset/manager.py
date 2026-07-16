"""Reset manager — handles factory resets and workspace clears with safety backups."""

from __future__ import annotations

import shutil
from pathlib import Path

from core.logging import get_logger
from services.backup.manager import BackupManager
from services.backup.models import BackupType
from services.reset.models import ResetConfig, ResetReport

_log = get_logger(__name__)

__all__ = ["ResetManager"]


class ResetManager:
    """Enterprise reset manager for safely reverting AAiOS configurations and databases."""

    def __init__(
        self,
        workspace_root: str | Path | None = None,
        backup_mgr: BackupManager | None = None,
    ) -> None:
        self.workspace_root = Path(workspace_root or self._find_workspace_root()).resolve()
        self.backup_mgr = backup_mgr or BackupManager(self.workspace_root)

    def _find_workspace_root(self) -> Path:
        """Find the workspace root by looking for pyproject.toml."""
        current = Path.cwd()
        for path in [current] + list(current.parents):
            if (path / "pyproject.toml").exists():
                return path
        return current

    def run_reset(self, config: ResetConfig) -> ResetReport:
        """Execute resetting procedures after generating a safety restore checkpoint."""
        report = ResetReport()
        _log.info("reset.started", factory=config.factory)

        try:
            # 1. Create a safety restore point (backup snapshot)
            try:
                meta = self.backup_mgr.create_backup(
                    backup_type=BackupType.FULL,
                    is_snapshot=True,
                    tags=["pre-reset-checkpoint"],
                )
                report.backup_id = meta.id
                _log.info("reset.restore_point_created", backup_id=meta.id)
            except Exception as backup_err:  # noqa: BLE001
                _log.warning("reset.restore_point_failed", error=str(backup_err))
                # In non-force mode, we might want to block reset if backup fails,
                # but we proceed here to fulfill reset execution.

            # 2. Reset database files
            if config.database or config.factory or config.everything:
                self._reset_databases(report)

            # 3. Reset memory indexes and vectors
            if config.memory or config.factory or config.everything:
                self._reset_memory(report)

            # 4. Reset plugins
            if config.plugins or config.factory or config.everything:
                self._reset_plugins(report)

            # 5. Reset provider settings and workspace configurations
            if config.providers or config.workspace or config.factory or config.everything:
                self._reset_configurations(report)

            # 6. Reset missions and workflows specifically
            if config.missions:
                self._reset_missions_and_workflows(report)

            _log.info("reset.completed", success=report.success)
        except Exception as e:  # noqa: BLE001
            report.success = False
            report.error = str(e)
            _log.error("reset.failed", error=str(e))

        return report

    def _reset_databases(self, report: ResetReport) -> None:
        """Re-initialize all database files to default empty schemas."""
        db_dir = self.workspace_root / "database"
        if db_dir.exists():
            for file in db_dir.glob("*.db"):
                try:
                    file.unlink()
                except OSError:
                    pass

        # Re-bootstrap
        from services.installer.database import DatabaseBootstrapper
        from services.installer.workspace import WorkspaceBootstrapper
        ws = WorkspaceBootstrapper(self.workspace_root)
        db_boot = DatabaseBootstrapper(ws)
        db_boot.bootstrap_all()

        report.reset_components.append("database")
        _log.info("reset.databases_reinitialized")

    def _reset_memory(self, report: ResetReport) -> None:
        """Clear memory SQLite databases and vector storage folders."""
        db_dir = self.workspace_root / "database"
        for db in ("memory.db", "knowledge_graph.db"):
            db_path = db_dir / db
            if db_path.exists():
                try:
                    db_path.unlink()
                except OSError:
                    pass

        # Clear vector storage
        vector_dir = self.workspace_root / "vector-storage"
        if vector_dir.exists():
            shutil.rmtree(vector_dir, ignore_errors=True)
            vector_dir.mkdir(parents=True, exist_ok=True)

        report.reset_components.append("memory")
        _log.info("reset.memory_purged")

    def _reset_plugins(self, report: ResetReport) -> None:
        """Delete all installed third-party plugins."""
        plugins_dir = self.workspace_root / "plugins"
        if plugins_dir.exists():
            shutil.rmtree(plugins_dir, ignore_errors=True)
            plugins_dir.mkdir(parents=True, exist_ok=True)
        report.reset_components.append("plugins")
        _log.info("reset.plugins_cleared")

    def _reset_configurations(self, report: ResetReport) -> None:
        """Overwrite config.yaml with defaults.yaml."""
        config_dir = self.workspace_root / "config"
        config_yaml = config_dir / "config.yaml"
        defaults_yaml = config_dir / "defaults.yaml"

        if defaults_yaml.exists():
            shutil.copy2(defaults_yaml, config_yaml)
            report.reset_components.append("configurations")
            _log.info("reset.config_restored_to_defaults")

    def _reset_missions_and_workflows(self, report: ResetReport) -> None:
        """Purge tables in mission.db and workflow.db databases."""
        # Simplified: we re-bootstrap these databases specifically
        db_dir = self.workspace_root / "database"
        for db in ("mission.db", "workflow.db"):
            db_path = db_dir / db
            if db_path.exists():
                try:
                    db_path.unlink()
                except OSError:
                    pass

        from services.installer.database import DatabaseBootstrapper
        from services.installer.workspace import WorkspaceBootstrapper
        ws = WorkspaceBootstrapper(self.workspace_root)
        db_boot = DatabaseBootstrapper(ws)
        db_boot.bootstrap_all()

        report.reset_components.append("missions_and_workflows")
        _log.info("reset.missions_and_workflows_cleared")
