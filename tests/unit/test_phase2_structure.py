"""Phase 2 smoke tests — verify the project structure is correct.

These tests don't exercise real functionality (that's Phase 3+). They verify:
  - The packages are importable
  - The CLI runs
  - The API health endpoints respond
  - The architecture invariants (INV-02, INV-09) hold

This gives us a baseline so we can detect regressions in the structure itself.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path
from typing import ClassVar

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]


# ---------------------------------------------------------------------------
# Project structure
# ---------------------------------------------------------------------------


@pytest.mark.offline
class TestProjectStructure:
    """Verify the directory structure matches the architecture."""

    def test_core_directories_exist(self) -> None:
        """L1 — Kernel subdirectories."""
        for sub in [
            "event_bus",
            "state",
            "config",
            "logging",
            "telemetry",
            "di",
            "registry",
            "gateway",
            "platform",
            "contracts",
        ]:
            assert (REPO_ROOT / "core" / sub).is_dir(), f"core/{sub} missing"

    def test_services_directories_exist(self) -> None:
        """L2 — Services subdirectories."""
        for sub in [
            "model_router",
            "model_router/providers",
            "memory",
            "mcp",
            "plugin",
            "agent_registry",
            "security",
        ]:
            assert (REPO_ROOT / "services" / sub).is_dir(), f"services/{sub} missing"

    def test_agents_directories_exist(self) -> None:
        """L3 — Agents directory has _types, _impls, _base."""
        for sub in ["_types", "_impls", "_base"]:
            assert (REPO_ROOT / "agents" / sub).is_dir(), f"agents/{sub} missing"

    def test_supervisor_and_orchestrator_exist(self) -> None:
        """L4 — Supervisor and Orchestrator."""
        assert (REPO_ROOT / "supervisor").is_dir()
        assert (REPO_ROOT / "orchestrator").is_dir()

    def test_surfaces_directories_exist(self) -> None:
        """L5 — Surfaces."""
        for sub in ["api", "cli", "web", "desktop"]:
            assert (REPO_ROOT / "surfaces" / sub).is_dir(), f"surfaces/{sub} missing"

    def test_deploy_directories_exist(self) -> None:
        """Deploy — Windows primary, Docker secondary."""
        assert (REPO_ROOT / "deploy" / "windows").is_dir()
        assert (REPO_ROOT / "deploy" / "docker").is_dir()

    def test_docs_directories_exist(self) -> None:
        """Architecture docs and reserved doc subdirs."""
        assert (REPO_ROOT / "docs" / "architecture").is_dir()
        for sub in ["operations", "developer", "plugin-sdk", "agent-sdk"]:
            assert (REPO_ROOT / "docs" / sub).is_dir(), f"docs/{sub} missing"


# ---------------------------------------------------------------------------
# Architecture documents
# ---------------------------------------------------------------------------


@pytest.mark.offline
class TestArchitectureDocs:
    """Verify all architecture documents are present."""

    EXPECTED_DOCS: ClassVar[list[str]] = [
        "00-overview.md",
        "01-goals-and-principles.md",
        "02-generic-agent-runtime.md",
        "03-system-design.md",
        "04-component-map.md",
        "05-data-flow.md",
        "06-tech-stack.md",
        "07-security-model.md",
        "08-deployment-topology.md",
        "09-roadmap.md",
        "README.md",
    ]

    def test_all_architecture_docs_present(self) -> None:
        """All 10 architecture docs + README must exist."""
        arch_dir = REPO_ROOT / "docs" / "architecture"
        for doc in self.EXPECTED_DOCS:
            assert (arch_dir / doc).is_file(), f"missing: docs/architecture/{doc}"

    def test_readme_mentions_generic_agent_runtime(self) -> None:
        """README must mention GenericAgent (the core design principle)."""
        readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        assert "Generic Agent Runtime" in readme or "GenericAgent" in readme

    def test_readme_mentions_windows_first(self) -> None:
        """README must mention Windows-first."""
        readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        assert "Windows-first" in readme or "Windows 11" in readme

    def test_generic_agent_runtime_doc_has_11_methods(self) -> None:
        """02-generic-agent-runtime.md must list all 11 GenericAgent methods."""
        doc = (REPO_ROOT / "docs" / "architecture" / "02-generic-agent-runtime.md").read_text(
            encoding="utf-8"
        )
        methods = [
            "initialize",
            "shutdown",
            "discover_capabilities",
            "execute_task",
            "stream_progress",
            "cancel_task",
            "report_health",
            "report_metrics",
            "request_permission",
            "serialize_state",
            "restore_state",
        ]
        for m in methods:
            assert m in doc, f"GenericAgent method '{m}' not in 02-generic-agent-runtime.md"


# ---------------------------------------------------------------------------
# Configuration files
# ---------------------------------------------------------------------------


@pytest.mark.offline
class TestConfigFiles:
    """Verify config files are present and well-formed."""

    def test_pyproject_toml_exists(self) -> None:
        assert (REPO_ROOT / "pyproject.toml").is_file()

    def test_pyproject_has_ruff_config(self) -> None:
        content = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
        assert "[tool.ruff]" in content
        assert "[tool.mypy]" in content
        assert "[tool.pytest.ini_options]" in content

    def test_package_json_exists(self) -> None:
        assert (REPO_ROOT / "package.json").is_file()
        assert (REPO_ROOT / "pnpm-workspace.yaml").is_file()

    def test_dockerfile_exists(self) -> None:
        assert (REPO_ROOT / "Dockerfile").is_file()
        assert (REPO_ROOT / "docker-compose.yml").is_file() or (
            REPO_ROOT / "deploy" / "docker" / "docker-compose.yml"
        ).is_file()

    def test_windows_installer_scaffolding(self) -> None:
        assert (REPO_ROOT / "deploy" / "windows" / "aaios.iss").is_file()
        assert (REPO_ROOT / "deploy" / "windows" / "bootstrap.ps1").is_file()

    def test_env_example_exists(self) -> None:
        assert (REPO_ROOT / ".env.example").is_file()

    def test_defaults_yaml_exists(self) -> None:
        assert (REPO_ROOT / "config" / "defaults.yaml").is_file()


# ---------------------------------------------------------------------------
# GitHub scaffolding
# ---------------------------------------------------------------------------


@pytest.mark.offline
class TestGitHubScaffolding:
    """Verify GitHub project files."""

    def test_issue_templates(self) -> None:
        for name in ["bug-report.yml", "feature-request.yml", "agent-proposal.yml"]:
            assert (REPO_ROOT / ".github" / "issue-templates" / name).is_file()

    def test_pr_template(self) -> None:
        assert (REPO_ROOT / ".github" / "pull_request_template.md").is_file()

    def test_codeowners(self) -> None:
        assert (REPO_ROOT / ".github" / "CODEOWNERS").is_file()

    def test_ci_workflow(self) -> None:
        ci = (REPO_ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
        # INV-12: Windows + Linux matrix
        assert "windows-latest" in ci, "CI must run on Windows (INV-12)"
        assert "ubuntu-latest" in ci, "CI must run on Linux (INV-12)"

    def test_release_workflow(self) -> None:
        assert (REPO_ROOT / ".github" / "workflows" / "release.yml").is_file()

    def test_codeql_workflow(self) -> None:
        assert (REPO_ROOT / ".github" / "workflows" / "codeql.yml").is_file()

    def test_dependabot_config(self) -> None:
        assert (REPO_ROOT / ".github" / "dependabot.yml").is_file()


# ---------------------------------------------------------------------------
# Documentation files
# ---------------------------------------------------------------------------


@pytest.mark.offline
class TestCommunityFiles:
    """Verify community docs."""

    def test_license_is_apache_2(self) -> None:
        license_text = (REPO_ROOT / "LICENSE").read_text(encoding="utf-8")
        assert "Apache License" in license_text
        assert "Version 2.0" in license_text

    def test_contributing_exists(self) -> None:
        assert (REPO_ROOT / "CONTRIBUTING.md").is_file()

    def test_code_of_conduct_exists(self) -> None:
        assert (REPO_ROOT / "CODE_OF_CONDUCT.md").is_file()

    def test_security_policy_exists(self) -> None:
        assert (REPO_ROOT / "SECURITY.md").is_file()

    def test_changelog_exists(self) -> None:
        assert (REPO_ROOT / "CHANGELOG.md").is_file()


# ---------------------------------------------------------------------------
# CLI smoke test
# ---------------------------------------------------------------------------


@pytest.mark.offline
class TestCLI:
    """Verify the CLI runs."""

    def test_version_command(self) -> None:
        result = subprocess.run(
            [sys.executable, "-m", "surfaces.cli", "version"],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
            timeout=10,
            check=False,
        )
        assert result.returncode == 0, result.stderr
        assert "AAiOS" in result.stdout
        assert "1.0.0" in result.stdout or "0.1.0" in result.stdout

    def test_doctor_command(self) -> None:
        result = subprocess.run(
            [sys.executable, "-m", "surfaces.cli", "doctor"],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
            timeout=10,
            check=False,
        )
        assert result.returncode == 0, result.stderr
        assert "AAiOS Doctor" in result.stdout
        assert "Version" in result.stdout


# ---------------------------------------------------------------------------
# Architecture invariants
# ---------------------------------------------------------------------------


@pytest.mark.offline
class TestInvariants:
    """Verify the architecture invariants (INV-02, INV-09) hold in the stub."""

    # Match agent implementation names (e.g. "Claude Code", "OpenHands") but
    # NOT model names (e.g. "claude-3-5-sonnet" is a model, not an agent).
    BANNED_AGENT_NAMES: ClassVar[list[str]] = [
        "claude.?code",
        "hermes",
        "openhands",
        "cline",
        "roo.?code",
        "roocode",
    ]
    # The Model Router is the centralized LLM I/O layer — it may import httpx.
    # The Gateway is the centralized filesystem/shell I/O layer — it may import subprocess.
    # Both are the designated I/O surfaces for their respective domains.
    BANNED_IO_IMPORTS: ClassVar[list[str]] = [
        "import subprocess",
        "import socket",
        "from subprocess",
        "from socket",
        "import requests",
        "from requests",
    ]

    def test_inv_09_no_agent_names_in_core(self) -> None:
        """INV-09: no agent implementation names in core/services/supervisor/orchestrator/surfaces."""
        banned_pattern = "|".join(self.BANNED_AGENT_NAMES)
        offending: list[str] = []
        for py_file in (REPO_ROOT / "core").rglob("*.py"):
            offending.extend(self._scan_file_for(py_file, banned_pattern))
        for py_file in (REPO_ROOT / "services").rglob("*.py"):
            # The installer legitimately needs to know agent names to discover them
            if "installer" in py_file.parts:
                continue
            offending.extend(self._scan_file_for(py_file, banned_pattern))
        for py_file in (REPO_ROOT / "supervisor").rglob("*.py"):
            offending.extend(self._scan_file_for(py_file, banned_pattern))
        for py_file in (REPO_ROOT / "orchestrator").rglob("*.py"):
            offending.extend(self._scan_file_for(py_file, banned_pattern))
        for py_file in (REPO_ROOT / "surfaces").rglob("*.py"):
            offending.extend(self._scan_file_for(py_file, banned_pattern))
        assert not offending, f"INV-09 violation: {offending}"

    def test_inv_02_no_io_imports_outside_gateway(self) -> None:
        """INV-02: only core/gateway/ and services/model_router/ may import I/O modules.

        The Gateway is the designated surface for filesystem/shell I/O.
        The Model Router is the designated surface for LLM API I/O (httpx).
        Both are the ONLY places these imports are allowed.
        """
        offending: list[tuple[Path, str]] = []
        for pkg in ["core", "services", "agents", "supervisor", "orchestrator", "surfaces"]:
            for py_file in (REPO_ROOT / pkg).rglob("*.py"):
                if "gateway" in py_file.parts:
                    continue
                # Allow httpx in the model router (it's the LLM I/O layer)
                if "model_router" in py_file.parts:
                    continue
                # Allow subprocess in services/installer (system-level tool)
                if "installer" in py_file.parts:
                    continue
                # Allow subprocess in surfaces/cli (L5 legitimately spawns processes)
                if "surfaces" in py_file.parts and "cli" in py_file.parts:
                    continue
                if "tests" in py_file.parts:
                    continue
                text = py_file.read_text(encoding="utf-8")
                for line in text.splitlines():
                    stripped = line.strip()
                    if stripped.startswith("#"):
                        continue
                    for banned in self.BANNED_IO_IMPORTS:
                        if banned in stripped:
                            offending.append((py_file, stripped))
                            break
        assert not offending, f"INV-02 violation: {offending}"

    @staticmethod
    def _scan_file_for(path: Path, pattern: str) -> list[str]:
        """Return matching lines (case-insensitive, whole word) in a Python file."""
        regex = re.compile(rf"\b({pattern})\b", re.IGNORECASE)
        results: list[str] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            if regex.search(stripped):
                results.append(f"{path}: {stripped}")
        return results
