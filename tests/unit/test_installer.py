"""Tests for AAiOS v5.3.2 — Installer.

Covers all 7 phases: environment discovery, dependency discovery,
workspace bootstrap, database bootstrap, configuration wizard,
provider configuration, and agent bootstrap. Plus the orchestrator.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from services.installer import (
    SUPPORTED_AGENTS,
    SUPPORTED_PROVIDERS,
    AgentBootstrapper,
    ConfigurationWizard,
    DatabaseBootstrapper,
    DependencyChecker,
    DependencyRegistry,
    DependencyStatus,
    EnvironmentDetector,
    InstallationMode,
    InstallationStage,
    InstallerOrchestrator,
    PlatformSupport,
    ProviderConfigurator,
    WorkspaceBootstrapper,
)
from services.installer.configuration import DEFAULT_PORTS
from services.installer.workspace import DEFAULT_WORKSPACE_DIRS

# ---------------------------------------------------------------------------
# Phase 1 — Environment Detector
# ---------------------------------------------------------------------------


@pytest.mark.offline
class TestEnvironmentDetector:
    """EnvironmentDetector tests."""

    def test_detect_returns_report(self) -> None:
        detector = EnvironmentDetector()
        report = detector.detect()
        assert report.os_name
        assert report.cpu_arch
        assert report.cpu_count > 0
        assert report.python_version  # we're running Python
        assert isinstance(report.path_entries, list)

    def test_detect_is_idempotent(self) -> None:
        detector = EnvironmentDetector()
        r1 = detector.detect()
        detector2 = EnvironmentDetector()
        r2 = detector2.detect()
        assert r1.os_name == r2.os_name
        assert r1.cpu_arch == r2.cpu_arch

    def test_assess_compatibility(self) -> None:
        detector = EnvironmentDetector()
        report = detector.detect()
        compat = detector.assess_compatibility(report)
        assert isinstance(compat.compatible, bool)
        assert isinstance(compat.blockers, list)
        assert isinstance(compat.warnings, list)

    def test_build_plan_interactive(self) -> None:
        detector = EnvironmentDetector()
        report = detector.detect()
        compat = detector.assess_compatibility(report)
        plan = detector.build_plan(
            report, compat, InstallationMode.INTERACTIVE, workspace_root="/tmp/aaios-test"
        )
        assert plan.mode == "interactive"
        assert len(plan.steps) > 0
        assert any(s.stage == InstallationStage.ENVIRONMENT_DISCOVERY.value for s in plan.steps)
        assert plan.workspace_root == "/tmp/aaios-test"

    def test_build_plan_minimal_skips_optional(self) -> None:
        detector = EnvironmentDetector()
        report = detector.detect()
        compat = detector.assess_compatibility(report)
        plan = detector.build_plan(
            report, compat, InstallationMode.MINIMAL, workspace_root="/tmp/aaios-min"
        )
        # Minimal mode skips provider and agent bootstrap
        stages = [s.stage for s in plan.steps]
        assert InstallationStage.PROVIDER_CONFIGURATION.value not in stages
        assert InstallationStage.AGENT_BOOTSTRAP.value not in stages

    def test_assess_risks(self) -> None:
        detector = EnvironmentDetector()
        report = detector.detect()
        compat = detector.assess_compatibility(report)
        risks = detector.assess_risks(report, compat)
        assert risks.overall_risk in ("info", "low", "medium", "high", "critical")
        assert isinstance(risks.risks, list)
        assert isinstance(risks.mitigations, list)

    def test_classify_platform_known(self) -> None:
        detector = EnvironmentDetector()
        assert detector._classify_platform("windows", "10.0.22631") == PlatformSupport.PRIMARY.value
        assert detector._classify_platform("linux", "5.15.0") in (
            PlatformSupport.SECONDARY.value,
            PlatformSupport.EXPERIMENTAL.value,
        )
        assert detector._classify_platform("darwin", "") == PlatformSupport.EXPERIMENTAL.value
        assert detector._classify_platform("unknown", "") == PlatformSupport.UNSUPPORTED.value

    def test_detection_errors_are_listed(self) -> None:
        detector = EnvironmentDetector()
        report = detector.detect()
        # detection_errors is a list (may be empty)
        assert isinstance(report.detection_errors, list)


# ---------------------------------------------------------------------------
# Phase 2 — Dependency Checker
# ---------------------------------------------------------------------------


@pytest.mark.offline
class TestDependencyChecker:
    """DependencyChecker tests."""

    def test_registry_has_specs(self) -> None:
        registry = DependencyRegistry()
        specs = registry.list_all()
        assert len(specs) > 10
        required = registry.list_required()
        assert any(s.name == "python" for s in required)
        assert any(s.name == "git" for s in required)

    def test_check_all_returns_results(self) -> None:
        checker = DependencyChecker()
        results = checker.check_all()
        assert len(results) > 10
        # Python should be present (we're running it)
        python_check = next(r for r in results if r.name == "python")
        assert python_check.status == DependencyStatus.PRESENT.value
        assert python_check.detected_version
        assert python_check.healthy

    def test_check_required_only(self) -> None:
        checker = DependencyChecker()
        results = checker.check_required()
        assert all(r.category == "required" for r in results)

    def test_check_optional_only(self) -> None:
        checker = DependencyChecker()
        results = checker.check_optional()
        assert all(r.category == "optional" for r in results)

    def test_optional_missing_does_not_fail(self) -> None:
        checker = DependencyChecker()
        results = checker.check_all()
        # Optional deps that are missing should have status MISSING (not raise)
        optional_missing = [
            r
            for r in results
            if r.category == "optional" and r.status == DependencyStatus.MISSING.value
        ]
        # It's OK to have missing optional deps
        assert isinstance(optional_missing, list)

    def test_install_missing_skips_optional(self) -> None:
        checker = DependencyChecker()
        checks = checker.check_all()
        updated = checker.install_missing(checks, skip_optional=True)
        # Optional missing should be marked OPTIONAL_SKIPPED
        for orig, upd in zip(checks, updated, strict=False):
            if orig.category == "optional" and orig.status == DependencyStatus.MISSING.value:
                assert upd.status == DependencyStatus.OPTIONAL_SKIPPED.value

    def test_version_gte(self) -> None:
        checker = DependencyChecker()
        assert checker._version_gte("3.12.1", "3.12")  # noqa: SLF001
        assert checker._version_gte("3.13.0", "3.12")  # noqa: SLF001
        assert not checker._version_gte("3.11.0", "3.12")  # noqa: SLF001
        assert checker._version_gte("2.45.1", "2.40")  # noqa: SLF001


# ---------------------------------------------------------------------------
# Phase 3 — Workspace Bootstrapper
# ---------------------------------------------------------------------------


@pytest.mark.offline
class TestWorkspaceBootstrapper:
    """WorkspaceBootstrapper tests."""

    def test_bootstrap_creates_all_dirs(self) -> None:
        with TemporaryDirectory() as d:
            bootstrapper = WorkspaceBootstrapper(d)
            layout = bootstrapper.bootstrap()
            assert layout.root == str(Path(d).resolve())
            # All default dirs should be created
            for dir_name in DEFAULT_WORKSPACE_DIRS:
                assert (Path(d) / dir_name).exists(), f"Missing: {dir_name}"
            assert len(layout.created_dirs) == len(DEFAULT_WORKSPACE_DIRS)

    def test_bootstrap_is_idempotent(self) -> None:
        with TemporaryDirectory() as d:
            bootstrapper = WorkspaceBootstrapper(d)
            bootstrapper.bootstrap()
            layout2 = bootstrapper.bootstrap()
            # Second run: all dirs already exist
            assert len(layout2.created_dirs) == 0
            assert len(layout2.existing_dirs) == len(DEFAULT_WORKSPACE_DIRS)

    def test_bootstrap_force_recreates(self) -> None:
        with TemporaryDirectory() as d:
            bootstrapper = WorkspaceBootstrapper(d)
            bootstrapper.bootstrap()
            layout = bootstrapper.bootstrap(force=True)
            # Force mode still treats them as existing (non-destructive)
            assert len(layout.existing_dirs) == len(DEFAULT_WORKSPACE_DIRS)

    def test_verify(self) -> None:
        with TemporaryDirectory() as d:
            bootstrapper = WorkspaceBootstrapper(d)
            bootstrapper.bootstrap()
            verification = bootstrapper.verify()
            assert all(verification.values())

    def test_create_restore_point(self) -> None:
        with TemporaryDirectory() as d:
            bootstrapper = WorkspaceBootstrapper(d)
            bootstrapper.bootstrap()
            rp_path = bootstrapper.create_restore_point("test-rp")
            assert Path(rp_path).exists()
            # The manifest should be valid JSON
            manifest = json.loads(Path(rp_path).read_text())
            assert isinstance(manifest, dict)

    def test_rollback_protects_user_data(self) -> None:
        with TemporaryDirectory() as d:
            bootstrapper = WorkspaceBootstrapper(d)
            bootstrapper.bootstrap()
            rp_path = bootstrapper.create_restore_point("before-changes")
            # Add a user file to projects/
            user_file = Path(d) / "projects" / "user-data.txt"
            user_file.write_text("important user data")
            # Add a non-user file to runtime/
            runtime_file = Path(d) / "runtime" / "cache.tmp"
            runtime_file.write_text("cache")
            # Rollback
            bootstrapper.rollback_to(rp_path)
            # User data should still exist
            assert user_file.exists()
            # Runtime cache should be removed
            assert not runtime_file.exists()

    def test_path_for(self) -> None:
        with TemporaryDirectory() as d:
            bootstrapper = WorkspaceBootstrapper(d)
            p = bootstrapper.path_for("config", "test.json")
            assert str(p).endswith("config/test.json")

    def test_ensure_dir(self) -> None:
        with TemporaryDirectory() as d:
            bootstrapper = WorkspaceBootstrapper(d)
            p = bootstrapper.ensure_dir("custom", "subdir")
            assert p.exists()


# ---------------------------------------------------------------------------
# Phase 4 — Database Bootstrapper
# ---------------------------------------------------------------------------


@pytest.mark.offline
class TestDatabaseBootstrapper:
    """DatabaseBootstrapper tests."""

    def test_bootstrap_all_creates_sqlite_dbs(self) -> None:
        with TemporaryDirectory() as d:
            ws = WorkspaceBootstrapper(d)
            ws.bootstrap()
            db = DatabaseBootstrapper(ws)
            results = db.bootstrap_all()
            # Should have results for every default DB + postgres + qdrant
            assert len(results) >= 11
            # All SQLite DBs should be migrated
            sqlite_results = [r for r in results if r.backend == "sqlite"]
            for r in sqlite_results:
                assert r.status in ("migrated", "verified")
                assert r.integrity_ok

    def test_sqlite_db_exists_after_bootstrap(self) -> None:
        with TemporaryDirectory() as d:
            ws = WorkspaceBootstrapper(d)
            ws.bootstrap()
            db = DatabaseBootstrapper(ws)
            db.bootstrap_all()
            db_path = ws.path_for("database", "audit.db")
            assert db_path.exists()

    def test_sqlite_schema_created(self) -> None:
        with TemporaryDirectory() as d:
            ws = WorkspaceBootstrapper(d)
            ws.bootstrap()
            db = DatabaseBootstrapper(ws)
            db.bootstrap_all()
            # Open the audit DB and check the table exists
            conn = sqlite3.connect(str(ws.path_for("database", "audit.db")))
            try:
                tables = conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table';"
                ).fetchall()
                table_names = [t[0] for t in tables]
                assert "audit_events" in table_names
            finally:
                conn.close()

    def test_verify_all(self) -> None:
        with TemporaryDirectory() as d:
            ws = WorkspaceBootstrapper(d)
            ws.bootstrap()
            db = DatabaseBootstrapper(ws)
            db.bootstrap_all()
            verification = db.verify_all()
            assert all(verification.values())

    def test_backup_all(self) -> None:
        with TemporaryDirectory() as d:
            ws = WorkspaceBootstrapper(d)
            ws.bootstrap()
            db = DatabaseBootstrapper(ws)
            db.bootstrap_all()
            backups = db.backup_all("test-backup")
            assert len(backups) > 0
            for path in backups.values():
                assert Path(path).exists()

    def test_idempotent_bootstrap(self) -> None:
        with TemporaryDirectory() as d:
            ws = WorkspaceBootstrapper(d)
            ws.bootstrap()
            db = DatabaseBootstrapper(ws)
            db.bootstrap_all()
            r2 = db.bootstrap_all()
            # Second run: no new migrations
            for result in r2:
                if result.backend == "sqlite":
                    # Either verified (no new migrations) or migrated (re-applied idempotently)
                    assert result.status in ("migrated", "verified")

    def test_get_stats(self) -> None:
        with TemporaryDirectory() as d:
            ws = WorkspaceBootstrapper(d)
            ws.bootstrap()
            db = DatabaseBootstrapper(ws)
            db.bootstrap_all()
            stats = db.get_stats()
            assert "audit" in stats
            assert stats["audit"]["exists"]
            assert "audit_events" in stats["audit"]["tables"]


# ---------------------------------------------------------------------------
# Phase 5 — Configuration Wizard
# ---------------------------------------------------------------------------


@pytest.mark.offline
class TestConfigurationWizard:
    """ConfigurationWizard tests."""

    def test_generate_development_profile(self) -> None:
        with TemporaryDirectory() as d:
            ws = WorkspaceBootstrapper(d)
            ws.bootstrap()
            wizard = ConfigurationWizard(ws)
            spec = wizard.generate("development")
            assert spec.profile == "development"
            assert spec.workspace_root == str(ws.root)
            assert "level" in spec.logging
            assert spec.logging["level"] == "DEBUG"

    def test_generate_production_profile(self) -> None:
        with TemporaryDirectory() as d:
            ws = WorkspaceBootstrapper(d)
            ws.bootstrap()
            wizard = ConfigurationWizard(ws)
            spec = wizard.generate("production")
            assert spec.profile == "production"
            assert spec.authentication["required"] is True
            assert spec.rbac["required"] is True

    def test_generate_enterprise_profile(self) -> None:
        with TemporaryDirectory() as d:
            ws = WorkspaceBootstrapper(d)
            ws.bootstrap()
            wizard = ConfigurationWizard(ws)
            spec = wizard.generate("enterprise")
            assert spec.profile == "enterprise"
            assert spec.security["strict_mode"] is True
            assert spec.security["encrypted_secrets"] is True
            assert spec.security["ssl_required"] is True

    def test_generate_minimal_profile(self) -> None:
        with TemporaryDirectory() as d:
            ws = WorkspaceBootstrapper(d)
            ws.bootstrap()
            wizard = ConfigurationWizard(ws)
            spec = wizard.generate("minimal")
            assert spec.profile == "minimal"
            assert spec.dashboard["enabled"] is False

    def test_generate_portable_profile(self) -> None:
        with TemporaryDirectory() as d:
            ws = WorkspaceBootstrapper(d)
            ws.bootstrap()
            wizard = ConfigurationWizard(ws)
            spec = wizard.generate("portable")
            assert spec.profile == "portable"
            assert spec.performance_profile.get("portable_mode") is True

    def test_save_and_load(self) -> None:
        with TemporaryDirectory() as d:
            ws = WorkspaceBootstrapper(d)
            ws.bootstrap()
            wizard = ConfigurationWizard(ws)
            spec = wizard.generate("development")
            path = wizard.save(spec)
            assert path.exists()
            loaded = wizard.load()
            assert loaded is not None
            assert loaded.profile == "development"

    def test_default_ports(self) -> None:
        assert DEFAULT_PORTS["api"] == 8000
        assert DEFAULT_PORTS["dashboard"] == 3000

    def test_overrides(self) -> None:
        with TemporaryDirectory() as d:
            ws = WorkspaceBootstrapper(d)
            ws.bootstrap()
            wizard = ConfigurationWizard(ws)
            spec = wizard.generate("development", overrides={"logging_level": "WARNING"})
            assert spec.logging["level"] == "WARNING"

    def test_interactive_mode_adds_prompts(self) -> None:
        with TemporaryDirectory() as d:
            ws = WorkspaceBootstrapper(d)
            ws.bootstrap()
            wizard = ConfigurationWizard(ws)
            spec = wizard.generate("development", interactive=True)
            assert "_prompts" in spec.performance_profile
            assert len(spec.performance_profile["_prompts"]) > 0


# ---------------------------------------------------------------------------
# Phase 6 — Provider Configurator
# ---------------------------------------------------------------------------


@pytest.mark.offline
class TestProviderConfigurator:
    """ProviderConfigurator tests."""

    def test_supported_providers_count(self) -> None:
        assert len(SUPPORTED_PROVIDERS) == 13

    def test_list_supported(self) -> None:
        with TemporaryDirectory() as d:
            configurator = ProviderConfigurator(workspace_root=d)
            providers = configurator.list_supported()
            assert len(providers) == 13
            names = [p["name"] for p in providers]
            assert "openai" in names
            assert "anthropic" in names
            assert "ollama" in names

    def test_discover_all_returns_checks(self) -> None:
        with TemporaryDirectory() as d:
            configurator = ProviderConfigurator(workspace_root=d)
            checks = configurator.discover_all()
            assert len(checks) == 13
            for c in checks:
                assert c.name
                assert isinstance(c.configured, bool)

    def test_configure_provider_with_api_key(self) -> None:
        with TemporaryDirectory() as d:
            configurator = ProviderConfigurator(workspace_root=d)
            check = configurator.configure_provider(
                "openai",
                api_key="sk-test-key-1234567890",
            )
            assert check.configured
            assert check.healthy
            assert check.enabled

    def test_configure_provider_without_required_key(self) -> None:
        with TemporaryDirectory() as d:
            configurator = ProviderConfigurator(workspace_root=d)
            check = configurator.configure_provider("openai")
            assert check.configured
            assert not check.healthy
            assert not check.enabled
            assert "API key" in (check.error or "")

    def test_configure_local_provider_no_key_needed(self) -> None:
        with TemporaryDirectory() as d:
            configurator = ProviderConfigurator(workspace_root=d)
            check = configurator.configure_provider("ollama")
            # Ollama doesn't need an API key — should be healthy
            assert check.configured
            assert check.healthy

    def test_provider_config_saved(self) -> None:
        with TemporaryDirectory() as d:
            configurator = ProviderConfigurator(workspace_root=d)
            configurator.configure_provider("openai", api_key="sk-test")
            config_path = Path(d) / "providers" / "openai.json"
            assert config_path.exists()
            config = json.loads(config_path.read_text())
            # The actual API key should never be saved
            assert "api_key" not in config
            assert config["api_key_set"] is True

    def test_disable_provider(self) -> None:
        with TemporaryDirectory() as d:
            configurator = ProviderConfigurator(workspace_root=d)
            configurator.configure_provider("openai", api_key="sk-test")
            assert configurator.disable_provider("openai")
            # Should now be disabled
            checks = configurator.discover_all()
            openai_check = next(c for c in checks if c.name == "openai")
            assert not openai_check.enabled

    def test_configure_fallback_routing(self) -> None:
        with TemporaryDirectory() as d:
            configurator = ProviderConfigurator(workspace_root=d)
            configurator.configure_provider("openai", api_key="sk-test", fallback_priority=1)
            configurator.configure_provider("anthropic", api_key="sk-test", fallback_priority=2)
            applied = configurator.configure_fallback_routing({"openai": 1, "anthropic": 2})
            assert applied == {"openai": 1, "anthropic": 2}


# ---------------------------------------------------------------------------
# Phase 7 — Agent Bootstrapper
# ---------------------------------------------------------------------------


@pytest.mark.offline
class TestAgentBootstrapper:
    """AgentBootstrapper tests."""

    def test_supported_agents_count(self) -> None:
        assert len(SUPPORTED_AGENTS) == 8

    def test_discover_all_returns_results(self) -> None:
        with TemporaryDirectory() as d:
            bootstrapper = AgentBootstrapper(workspace_root=d)
            results = bootstrapper.discover_all()
            assert len(results) == 8
            for r in results:
                assert r.name
                assert r.display_name

    def test_discover_one(self) -> None:
        with TemporaryDirectory() as d:
            bootstrapper = AgentBootstrapper(workspace_root=d)
            result = bootstrapper.discover_one("claude-code")
            assert result is not None
            assert result.name == "claude-code"

    def test_discover_one_unknown(self) -> None:
        with TemporaryDirectory() as d:
            bootstrapper = AgentBootstrapper(workspace_root=d)
            result = bootstrapper.discover_one("unknown-agent")
            assert result is None

    def test_register_all_writes_records(self) -> None:
        with TemporaryDirectory() as d:
            bootstrapper = AgentBootstrapper(workspace_root=d)
            results = bootstrapper.discover_all()
            registered = bootstrapper.register_all(results)
            # At least some agents may be discovered (depends on host)
            for name in registered:
                record_path = Path(d) / "agents" / f"{name}.json"
                assert record_path.exists()
                record = json.loads(record_path.read_text())
                assert record["name"] == name

    def test_generate_manifests(self) -> None:
        with TemporaryDirectory() as d:
            bootstrapper = AgentBootstrapper(workspace_root=d)
            results = bootstrapper.discover_all()
            manifests = bootstrapper.generate_manifests(results)
            # Only discovered agents get manifests
            for name, manifest in manifests.items():
                assert manifest["name"] == name
                assert manifest["manifest_version"] == "1.0"
                assert "capabilities" in manifest


# ---------------------------------------------------------------------------
# InstallerOrchestrator
# ---------------------------------------------------------------------------


@pytest.mark.offline
class TestInstallerOrchestrator:
    """InstallerOrchestrator facade tests."""

    async def test_install_minimal_succeeds(self) -> None:
        with TemporaryDirectory() as d:
            orchestrator = InstallerOrchestrator(workspace_root=d)
            report = await orchestrator.install(
                mode=InstallationMode.MINIMAL,
                workspace_root=d,
            )
            assert report.mode == "minimal"
            assert report.overall_status in ("success", "partial")
            assert report.workspace is not None
            assert len(report.databases) > 0
            assert report.restore_point_path  # restore point created

    async def test_install_creates_workspace(self) -> None:
        with TemporaryDirectory() as d:
            ws_root = str(Path(d) / "aaios-ws")
            orchestrator = InstallerOrchestrator(workspace_root=ws_root)
            await orchestrator.install(
                mode=InstallationMode.MINIMAL,
                workspace_root=ws_root,
            )
            assert Path(ws_root).exists()
            # All default dirs should be created
            for dir_name in DEFAULT_WORKSPACE_DIRS:
                assert (Path(ws_root) / dir_name).exists()

    async def test_install_creates_databases(self) -> None:
        with TemporaryDirectory() as d:
            orchestrator = InstallerOrchestrator(workspace_root=d)
            await orchestrator.install(
                mode=InstallationMode.MINIMAL,
                workspace_root=d,
            )
            # At least one SQLite database should exist
            db_dir = Path(d) / "database"
            assert db_dir.exists()
            db_files = list(db_dir.glob("*.db"))
            assert len(db_files) > 0

    async def test_install_saves_report(self) -> None:
        with TemporaryDirectory() as d:
            orchestrator = InstallerOrchestrator(workspace_root=d)
            report = await orchestrator.install(
                mode=InstallationMode.MINIMAL,
                workspace_root=d,
            )
            assert report.log_path
            assert Path(report.log_path).exists()
            saved = json.loads(Path(report.log_path).read_text())
            assert saved["mode"] == "minimal"

    async def test_install_saves_config(self) -> None:
        with TemporaryDirectory() as d:
            orchestrator = InstallerOrchestrator(workspace_root=d)
            await orchestrator.install(
                mode=InstallationMode.MINIMAL,
                workspace_root=d,
            )
            config_path = Path(d) / "config" / "config.json"
            assert config_path.exists()
            config = json.loads(config_path.read_text())
            assert config["profile"]  # some profile should be set

    async def test_install_is_idempotent(self) -> None:
        with TemporaryDirectory() as d:
            orchestrator = InstallerOrchestrator(workspace_root=d)
            r1 = await orchestrator.install(
                mode=InstallationMode.MINIMAL,
                workspace_root=d,
            )
            r2 = await orchestrator.install(
                mode=InstallationMode.MINIMAL,
                workspace_root=d,
            )
            assert r1.overall_status in ("success", "partial")
            assert r2.overall_status in ("success", "partial")

    async def test_validate_mode(self) -> None:
        with TemporaryDirectory() as d:
            orchestrator = InstallerOrchestrator(workspace_root=d)
            # First install
            await orchestrator.install(
                mode=InstallationMode.MINIMAL,
                workspace_root=d,
            )
            # Then validate
            report = await orchestrator.validate()
            assert report.mode == "validate"
            assert report.overall_status in ("success", "partial")

    async def test_install_force_overrides_blockers(self) -> None:
        with TemporaryDirectory() as d:
            orchestrator = InstallerOrchestrator(workspace_root=d)
            report = await orchestrator.install(
                mode=InstallationMode.FORCE,
                workspace_root=d,
                force=True,
            )
            # Force mode should succeed even with compatibility blockers
            assert report.overall_status in ("success", "partial")
