"""Unit tests for Part 3 enterprise services (Uninstall, Reset, Cleanup, Packaging, Certify, Benchmark)."""

from __future__ import annotations

import tempfile
from pathlib import Path

from services.benchmark.manager import BenchmarkManager
from services.certify.manager import CertifyManager
from services.cleanup.manager import CleanupManager
from services.cleanup.models import CleanupConfig
from services.packaging.manager import PackagingManager
from services.reset.manager import ResetManager
from services.reset.models import ResetConfig
from services.uninstall.manager import UninstallManager
from services.uninstall.models import UninstallConfig


def test_uninstall_manager() -> None:
    """Test UninstallManager functionality."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        workspace_path = Path(tmp_dir)

        # Setup mock directories
        (workspace_path / "database").mkdir()
        (workspace_path / "caches").mkdir()
        (workspace_path / "pyproject.toml").write_text("", encoding="utf-8")

        manager = UninstallManager(workspace_root=workspace_path)
        config = UninstallConfig(
            silent=True,
            remove_data=True,
            remove_cache=True,
        )

        report = manager.run_uninstall(config)
        assert report.success
        assert not (workspace_path / "database").exists()
        assert not (workspace_path / "caches").exists()


def test_reset_manager() -> None:
    """Test ResetManager safety restore point and reset actions."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        workspace_path = Path(tmp_dir)
        (workspace_path / "pyproject.toml").write_text("", encoding="utf-8")
        (workspace_path / "config").mkdir()
        (workspace_path / "config" / "config.yaml").write_text("key: val", encoding="utf-8")
        (workspace_path / "config" / "defaults.yaml").write_text("key: default", encoding="utf-8")
        (workspace_path / "backups").mkdir()

        manager = ResetManager(workspace_root=workspace_path)
        config = ResetConfig(factory=True)

        report = manager.run_reset(config)
        assert report.success
        # Verify defaults are restored
        assert (workspace_path / "config" / "config.yaml").read_text(encoding="utf-8") == "key: default"


def test_cleanup_manager() -> None:
    """Test CleanupManager space reclamation."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        workspace_path = Path(tmp_dir)
        (workspace_path / "pyproject.toml").write_text("", encoding="utf-8")
        (workspace_path / "caches").mkdir()
        test_cache = workspace_path / "caches" / "old_cache.txt"
        test_cache.write_text("some_cache_data", encoding="utf-8")

        manager = CleanupManager(workspace_root=workspace_path)
        config = CleanupConfig(cache=True)

        # Dry-run
        report_dry = manager.run_cleanup(CleanupConfig(dry_run=True, cache=True))
        assert report_dry.success
        assert report_dry.reclaimed_bytes > 0
        assert test_cache.exists()

        # Real run
        report = manager.run_cleanup(config)
        assert report.success
        assert not test_cache.exists()


def test_packaging_manager() -> None:
    """Test PackagingManager zip archives and SBOM generation."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        workspace_path = Path(tmp_dir)
        (workspace_path / "pyproject.toml").write_text("[tool.poetry]", encoding="utf-8")

        manager = PackagingManager(workspace_root=workspace_path)
        manifest = manager.build_release("5.3.2")

        assert len(manifest.packages) > 0
        # Check ZIP files were created
        for pkg in manifest.packages:
            assert (workspace_path / "releases" / pkg.filename).exists()


def test_certify_manager() -> None:
    """Test CertifyManager compliance audits and certificates generation."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        workspace_path = Path(tmp_dir)
        (workspace_path / "pyproject.toml").write_text("", encoding="utf-8")
        (workspace_path / "database").mkdir()
        (workspace_path / "database" / "memory.db").write_text("", encoding="utf-8")

        manager = CertifyManager(workspace_root=workspace_path)
        res = manager.run_certification()

        assert res.production_cert != ""
        assert res.security_cert != ""
        assert (workspace_path / "reports" / "compliance_certificates.txt").exists()


def test_benchmark_manager() -> None:
    """Test BenchmarkManager latencies collection."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        workspace_path = Path(tmp_dir)
        (workspace_path / "pyproject.toml").write_text("", encoding="utf-8")

        manager = BenchmarkManager(workspace_root=workspace_path)
        res = manager.run_benchmark()

        assert res.cold_boot_ms > 0.0
        assert res.database_latency_ms >= 0.0
        assert (workspace_path / "reports" / "benchmark_report.json").exists()
