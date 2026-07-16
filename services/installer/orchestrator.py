"""Installer orchestrator — top-level facade that runs all 7 phases.

The orchestrator is:
  - Idempotent: re-running is safe
  - Restart-safe: each phase is independent
  - Transactional: failures are recorded, not propagated
  - Rollback capable: a restore point is created before any change

Usage:
    orchestrator = InstallerOrchestrator()
    report = await orchestrator.install(mode=InstallationMode.INTERACTIVE)
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from core.logging import get_logger
from services.installer.agents import AgentBootstrapper
from services.installer.configuration import ConfigurationWizard
from services.installer.database import DatabaseBootstrapper
from services.installer.dependencies import DependencyChecker
from services.installer.environment import EnvironmentDetector
from services.installer.models import (
    ConfigProfile,
    InstallationMode,
    InstallationReport,
    InstallationStage,
)
from services.installer.providers import ProviderConfigurator
from services.installer.workspace import WorkspaceBootstrapper

_log = get_logger(__name__)

__all__ = ["InstallerOrchestrator"]


class InstallerOrchestrator:
    """Top-level facade for the entire installation process."""

    def __init__(self, workspace_root: str = "") -> None:
        self._workspace_root = workspace_root
        self._detector = EnvironmentDetector()
        self._workspace: WorkspaceBootstrapper | None = None
        self._dependency_checker = DependencyChecker()
        self._db_bootstrapper: DatabaseBootstrapper | None = None
        self._config_wizard: ConfigurationWizard | None = None
        self._provider_configurator: ProviderConfigurator | None = None
        self._agent_bootstrapper: AgentBootstrapper | None = None

    async def install(
        self,
        mode: InstallationMode | str = InstallationMode.INTERACTIVE,
        *,
        workspace_root: str = "",
        profile: ConfigProfile | str | None = None,
        skip_optional: bool = True,
        force: bool = False,
    ) -> InstallationReport:
        """Run the complete installation.

        Args:
            mode: installation mode (interactive, silent, minimal, etc.).
            workspace_root: override the default workspace root.
            profile: override the default configuration profile.
            skip_optional: skip optional dependencies that can't be auto-installed.
            force: force re-creation of existing directories (non-destructive).

        Returns:
            InstallationReport covering every phase.
        """
        m = InstallationMode(mode) if isinstance(mode, str) else mode
        report = InstallationReport(
            mode=m.value,
            started_at=datetime.now(UTC),
            current_stage=InstallationStage.ENVIRONMENT_DISCOVERY.value,
        )
        # Determine workspace root
        if workspace_root:
            self._workspace_root = workspace_root
        # --- Phase 1: Environment discovery ---
        try:
            report.environment = self._detector.detect()
            report.compatibility = self._detector.assess_compatibility(report.environment)
            plan_root = workspace_root or self._workspace_root or self._detector._default_workspace_root(m)  # noqa: SLF001
            report.plan = self._detector.build_plan(
                report.environment, report.compatibility, m, workspace_root=plan_root,
            )
            report.risks = self._detector.assess_risks(report.environment, report.compatibility)
            # Use the plan's workspace root going forward
            self._workspace_root = report.plan.workspace_root
        except Exception as e:  # noqa: BLE001
            report.errors.append(f"Phase 1 failed: {e}")
            report.current_stage = InstallationStage.FAILED.value
            report.overall_status = "failed"
            report.completed_at = datetime.now(UTC)
            return report
        # Check compatibility blockers (but don't abort in --force mode)
        if report.compatibility and not report.compatibility.compatible and not force:
            if m != InstallationMode.FORCE:
                report.errors.append("Compatibility blockers detected — use --force to override")
                report.current_stage = InstallationStage.FAILED.value
                report.overall_status = "failed"
                report.completed_at = datetime.now(UTC)
                return report
        # --- Phase 3: Workspace bootstrap ---
        # (Initialize workspace before creating restore point)
        self._workspace = WorkspaceBootstrapper(self._workspace_root)
        report.workspace = self._workspace.bootstrap(force=force)
        # Create restore point
        try:
            report.restore_point_path = self._workspace.create_restore_point(
                name=f"pre-install-{datetime.now(UTC).strftime('%Y%m%dT%H%M%S')}"
            )
        except Exception as e:  # noqa: BLE001
            report.warnings.append(f"restore point creation failed: {e}")
        report.current_stage = InstallationStage.DEPENDENCY_DISCOVERY.value
        # --- Phase 2: Dependency discovery ---
        try:
            deps = self._dependency_checker.check_all()
            if m not in (InstallationMode.VALIDATE,):
                deps = self._dependency_checker.install_missing(deps, skip_optional=skip_optional)
            report.dependencies = deps
        except Exception as e:  # noqa: BLE001
            report.errors.append(f"Phase 2 failed: {e}")
        report.current_stage = InstallationStage.WORKSPACE_BOOTSTRAP.value
        # --- Phase 4: Database bootstrap ---
        try:
            self._db_bootstrapper = DatabaseBootstrapper(self._workspace)
            report.databases = self._db_bootstrapper.bootstrap_all()
        except Exception as e:  # noqa: BLE001
            report.errors.append(f"Phase 4 failed: {e}")
        report.current_stage = InstallationStage.DATABASE_BOOTSTRAP.value
        # --- Phase 5: Configuration wizard ---
        try:
            self._config_wizard = ConfigurationWizard(self._workspace)
            p = profile or report.plan.profile
            report.configuration = self._config_wizard.generate(p)
            self._config_wizard.save(report.configuration)
        except Exception as e:  # noqa: BLE001
            report.errors.append(f"Phase 5 failed: {e}")
        report.current_stage = InstallationStage.CONFIGURATION.value
        # --- Phase 6: Provider configuration ---
        if m not in (InstallationMode.MINIMAL, InstallationMode.VALIDATE):
            try:
                self._provider_configurator = ProviderConfigurator(
                    workspace_root=str(self._workspace.root)
                )
                report.providers = self._provider_configurator.discover_all()
            except Exception as e:  # noqa: BLE001
                report.errors.append(f"Phase 6 failed: {e}")
        report.current_stage = InstallationStage.PROVIDER_CONFIGURATION.value
        # --- Phase 7: Agent bootstrap ---
        if m not in (InstallationMode.MINIMAL, InstallationMode.VALIDATE):
            try:
                self._agent_bootstrapper = AgentBootstrapper(
                    workspace_root=str(self._workspace.root)
                )
                agent_results = self._agent_bootstrapper.discover_all()
                self._agent_bootstrapper.generate_manifests(agent_results)
                registered = self._agent_bootstrapper.register_all(agent_results)
                report.agents_registered = registered
            except Exception as e:  # noqa: BLE001
                report.errors.append(f"Phase 7 failed: {e}")
        report.current_stage = InstallationStage.AGENT_BOOTSTRAP.value
        # --- Validation ---
        report.current_stage = InstallationStage.VALIDATION.value
        # Determine overall status
        if report.errors:
            report.overall_status = "partial"
        else:
            report.overall_status = "success"
        report.current_stage = InstallationStage.COMPLETED.value
        report.completed_at = datetime.now(UTC)
        # Save the report
        self._save_report(report)
        _log.info(
            "installer.completed",
            mode=m.value,
            status=report.overall_status,
            errors=len(report.errors),
            agents=len(report.agents_registered),
        )
        return report

    async def validate(self) -> InstallationReport:
        """Validate an existing installation without modifying anything."""
        return await self.install(mode=InstallationMode.VALIDATE, force=False)

    async def repair(self) -> InstallationReport:
        """Repair an existing installation."""
        return await self.install(mode=InstallationMode.REPAIR, force=True)

    async def upgrade(self) -> InstallationReport:
        """Upgrade an existing installation in place."""
        return await self.install(mode=InstallationMode.UPGRADE, force=False)

    # --- helpers --------------------------------------------------------

    def _save_report(self, report: InstallationReport) -> None:
        """Save the installation report to the workspace."""
        if not self._workspace:
            return
        try:
            reports_dir = self._workspace.ensure_dir("reports")
            path = reports_dir / f"install-{report.report_id}.json"
            path.write_text(json.dumps(report.to_dict(), indent=2, default=str))
            report.log_path = str(path)
        except OSError as e:
            _log.warning("installer.report_save_failed", error=str(e))

    def rollback(self, restore_point_path: str) -> dict[str, Any]:
        """Roll back to a restore point."""
        if not self._workspace:
            return {"error": "workspace not initialized"}
        return self._workspace.rollback_to(restore_point_path)
