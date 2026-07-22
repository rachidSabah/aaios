"""Unit tests for the enterprise administration, diagnostic, and recovery services (Part 2)."""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

import pytest

from services.backup.manager import BackupManager
from services.backup.models import BackupType, ExportFormat
from services.backup.recovery import RecoveryManager
from services.doctor.manager import DoctorManager
from services.doctor.models import ScanType
from services.monitoring.models import AlertChannel
from services.monitoring.monitor import ContinuousHealthMonitor
from services.self_healing.engine import SelfHealingEngine
from services.update.manager import UpdateManager
from services.update.models import ReleaseChannel
from services.validator.manager import ReleaseValidator


@pytest.fixture
def temp_workspace():
    """Create a temporary directory simulating the AAIOS workspace root."""
    temp_dir = tempfile.mkdtemp()
    workspace = Path(temp_dir)

    # Create basic directory structure
    (workspace / "config").mkdir(parents=True, exist_ok=True)
    (workspace / "database").mkdir(parents=True, exist_ok=True)
    (workspace / "secrets").mkdir(parents=True, exist_ok=True)
    (workspace / "pyproject.toml").write_text("[tool.ruff]\n", encoding="utf-8")

    yield workspace

    shutil.rmtree(temp_dir, ignore_errors=True)


def test_doctor_scan(temp_workspace):
    """Test that DoctorManager correctly runs scans and identifies missing directories."""
    doctor = DoctorManager(temp_workspace)
    report = doctor.run_scan(ScanType.QUICK)

    assert report is not None
    assert (
        report.health_score < 100
    )  # Some directories/files should be missing in empty temp workspace

    # Check that config missing is in issues
    issues_ids = [issue.id for issue in report.issues]
    assert "CONFIG_YAML_MISSING" in issues_ids


@pytest.mark.asyncio
async def test_self_healing(temp_workspace):
    """Test that SelfHealingEngine can automatically correct missing configuration yaml."""
    doctor = DoctorManager(temp_workspace)
    engine = SelfHealingEngine(temp_workspace, doctor_mgr=doctor)

    # Create defaults.yaml so config.yaml can be healed
    (temp_workspace / "config" / "defaults.yaml").write_text("env: test\n", encoding="utf-8")

    records = await engine.run_healing(auto_approve=True)
    assert len(records) > 0

    # Assert that config.yaml was successfully restored
    assert (temp_workspace / "config" / "config.yaml").exists()
    assert (temp_workspace / "config" / "config.yaml").read_text(encoding="utf-8") == "env: test\n"


def test_backup_and_restore(temp_workspace):
    """Test that BackupManager and RecoveryManager can create and restore backups."""
    backup_mgr = BackupManager(temp_workspace)
    recovery_mgr = RecoveryManager(temp_workspace, backup_mgr)

    # Write a test file in secrets
    test_file = temp_workspace / "secrets" / "test_api.key"
    test_file.write_text("secret_key_123", encoding="utf-8")

    # Create a full zip backup
    meta = backup_mgr.create_backup(BackupType.FULL, ExportFormat.ZIP, encrypt=False, tags=["test"])
    assert meta is not None
    assert (temp_workspace / "backups" / f"backup-{meta.id}.zip").exists()

    # Modify the test file
    test_file.write_text("corrupted_key", encoding="utf-8")

    # Restore the backup
    import asyncio

    report = asyncio.run(recovery_mgr.restore_backup(meta.id))
    assert report.success

    # Verify that the test file was successfully restored
    assert test_file.read_text(encoding="utf-8") == "secret_key_123"


def test_snapshot_compare(temp_workspace):
    """Test snapshot comparison functionality."""
    backup_mgr = BackupManager(temp_workspace)

    # Take Snapshot A
    snap_a = backup_mgr.create_backup(BackupType.FULL, ExportFormat.ZIP, is_snapshot=True)

    # Create a new file in config
    new_cfg = temp_workspace / "config" / "new_val.yaml"
    new_cfg.write_text("foo: bar", encoding="utf-8")

    # Take Snapshot B
    snap_b = backup_mgr.create_backup(BackupType.FULL, ExportFormat.ZIP, is_snapshot=True)

    # Compare
    diff = backup_mgr.compare_snapshots(snap_a.id, snap_b.id)

    assert str(Path("config/new_val.yaml")) in diff["added"]


def test_release_channel_updates(temp_workspace):
    """Test checking and pinning version in UpdateManager."""
    update_mgr = UpdateManager(temp_workspace)

    # Check stable updates
    info = update_mgr.check_for_updates(ReleaseChannel.STABLE)
    assert info is not None
    assert info.version == "5.3.3"

    # Pin version
    update_mgr.pin_version("5.3.2")
    info_pinned = update_mgr.check_for_updates(ReleaseChannel.STABLE)
    assert info_pinned is None


def test_release_validator(temp_workspace):
    """Test ReleaseValidator reports and deployment readiness scores."""
    validator = ReleaseValidator(temp_workspace)
    report = validator.run_validation()

    assert report is not None
    assert report.runtime_ok

    # Verify readiness score is calculated correctly
    readiness = validator.generate_readiness_report(report)
    assert readiness.readiness_score <= 100


def test_health_monitor(temp_workspace):
    """Test health metrics collection and rule evaluation."""
    monitor = ContinuousHealthMonitor(temp_workspace)

    # Configure alerts
    monitor.configure_channel(AlertChannel.CLI, "stdout")

    metrics = monitor.collect_metrics()
    assert metrics.cpu_percent >= 0.0
    assert metrics.disk_free_gb >= 0.0

    # Check component evaluations
    statuses = monitor.check_components()
    assert len(statuses) > 0

    # Evaluate rules
    alerts = monitor.evaluate_rules(metrics, statuses)
    assert isinstance(alerts, list)
