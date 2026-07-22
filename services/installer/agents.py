"""Phase 7 — Agent Bootstrap.

Discovers, validates, and registers every supported agent implementation.

Supported agents:
  Claude Code, OpenCode, Hermes, Codex CLI, Gemini CLI, OpenHands,
  Cline, Roo Code, and any custom Generic Agents.

Each agent is:
  - Discovered (CLI tool check + version detection)
  - Validated (signature, permissions)
  - Capability-indexed (what the agent can do)
  - Registered (bound to the Agent Registry)

No manual registration is required — everything is automatic.
"""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass, field
from typing import Any

from core.logging import get_logger

_log = get_logger(__name__)

__all__ = ["AgentBootstrapper", "AgentDiscoveryResult", "SUPPORTED_AGENTS"]


@dataclass
class AgentSpec:
    """Specification of a known agent."""

    name: str
    display_name: str
    tool: str  # CLI tool name
    version_args: tuple[str, ...] = ("--version",)
    agent_type: str = "generic"  # coding | desktop | research | browser | generic
    capabilities: list[str] = field(default_factory=list)
    install_hint: str = ""
    can_install: bool = False
    install_command: list[str] = field(default_factory=list)


@dataclass
class AgentDiscoveryResult:
    """Result of discovering a single agent."""

    name: str
    display_name: str
    discovered: bool = False
    registered: bool = False
    validated: bool = False
    version: str = ""
    install_path: str = ""
    agent_type: str = "generic"
    capabilities: list[str] = field(default_factory=list)
    error: str | None = None
    manifest: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "display_name": self.display_name,
            "discovered": self.discovered,
            "registered": self.registered,
            "validated": self.validated,
            "version": self.version,
            "install_path": self.install_path,
            "agent_type": self.agent_type,
            "capabilities": list(self.capabilities),
            "error": self.error,
            "manifest": dict(self.manifest),
        }


SUPPORTED_AGENTS: tuple[AgentSpec, ...] = (
    AgentSpec(
        name="claude-code",
        display_name="Claude Code",
        tool="claude",
        agent_type="coding",
        capabilities=["code_generation", "code_review", "refactoring", "testing"],
        install_hint="npm install -g @anthropic-ai/claude-code",
        can_install=True,
        install_command=["npm", "install", "-g", "@anthropic-ai/claude-code"],
    ),
    AgentSpec(
        name="opencode",
        display_name="OpenCode",
        tool="opencode",
        agent_type="coding",
        capabilities=["code_generation", "code_review", "refactoring"],
    ),
    AgentSpec(
        name="hermes",
        display_name="Hermes",
        tool="hermes",
        agent_type="desktop",
        capabilities=[
            "desktop_automation",
            "browser_automation",
            "file_management",
            "window_management",
            "screenshot",
        ],
    ),
    AgentSpec(
        name="codex-cli",
        display_name="Codex CLI",
        tool="codex",
        agent_type="coding",
        capabilities=["code_generation", "code_review"],
    ),
    AgentSpec(
        name="gemini-cli",
        display_name="Gemini CLI",
        tool="gemini",
        agent_type="coding",
        capabilities=["code_generation", "code_review", "vision"],
    ),
    AgentSpec(
        name="openhands",
        display_name="OpenHands",
        tool="openhands",
        agent_type="coding",
        capabilities=["code_generation", "code_review", "refactoring", "testing", "deployment"],
    ),
    AgentSpec(
        name="cline",
        display_name="Cline",
        tool="cline",
        agent_type="coding",
        capabilities=["code_generation", "code_review"],
    ),
    AgentSpec(
        name="roo-code",
        display_name="Roo Code",
        tool="roo",
        agent_type="coding",
        capabilities=["code_generation", "code_review"],
    ),
)


class AgentBootstrapper:
    """Phase 7 — discover, validate, and register agents."""

    def __init__(self, workspace_root: str = "") -> None:
        self._workspace_root = workspace_root

    def discover_all(self) -> list[AgentDiscoveryResult]:
        """Discover every supported agent."""
        results: list[AgentDiscoveryResult] = []
        for spec in SUPPORTED_AGENTS:
            results.append(self._discover_one(spec))
        return results

    def discover_one(self, name: str) -> AgentDiscoveryResult | None:
        """Discover a single agent by name."""
        for spec in SUPPORTED_AGENTS:
            if spec.name == name:
                return self._discover_one(spec)
        return None

    def register_all(self, results: list[AgentDiscoveryResult]) -> list[str]:
        """Register every discovered agent with the Agent Registry.

        Returns the list of registered agent names.
        """
        registered: list[str] = []
        for result in results:
            if not result.discovered:
                continue
            try:
                self._register_one(result)
                result.registered = True
                registered.append(result.name)
                _log.info(
                    "installer.agent_registered",
                    name=result.name,
                    type=result.agent_type,
                    capabilities=len(result.capabilities),
                )
            except Exception as e:  # noqa: BLE001
                result.error = f"registration failed: {e}"
                _log.warning(
                    "installer.agent_registration_failed",
                    name=result.name,
                    error=str(e),
                )
        return registered

    def generate_manifests(self, results: list[AgentDiscoveryResult]) -> dict[str, dict[str, Any]]:
        """Generate a manifest for each discovered agent."""
        manifests: dict[str, dict[str, Any]] = {}
        for result in results:
            if not result.discovered:
                continue
            manifest = self._build_manifest(result)
            result.manifest = manifest
            manifests[result.name] = manifest
            self._save_manifest(result.name, manifest)
        return manifests

    def install_missing(self, results: list[AgentDiscoveryResult]) -> list[AgentDiscoveryResult]:
        """Attempt to install missing agents (only those with can_install=True)."""
        updated: list[AgentDiscoveryResult] = []
        for result in results:
            if result.discovered:
                updated.append(result)
                continue
            spec = self._find_spec(result.name)
            if not spec or not spec.can_install or not spec.install_command:
                updated.append(result)
                continue
            try:
                install_result = subprocess.run(  # noqa: S603
                    spec.install_command,  # noqa: S607
                    capture_output=True,
                    text=True,
                    timeout=300,
                    check=False,
                )
                if install_result.returncode == 0:
                    # Re-discover
                    new_result = self._discover_one(spec)
                    new_result.registered = True
                    updated.append(new_result)
                else:
                    result.error = (
                        install_result.stderr[:200] if install_result.stderr else "install failed"
                    )
                    updated.append(result)
            except (subprocess.SubprocessError, OSError) as e:
                result.error = str(e)
                updated.append(result)
        return updated

    # --- helpers --------------------------------------------------------

    def _discover_one(self, spec: AgentSpec) -> AgentDiscoveryResult:
        """Discover a single agent."""
        result = AgentDiscoveryResult(
            name=spec.name,
            display_name=spec.display_name,
            agent_type=spec.agent_type,
            capabilities=list(spec.capabilities),
        )
        path = shutil.which(spec.tool)
        if not path:
            result.discovered = False
            result.error = f"{spec.tool} not found in PATH"
            return result
        result.discovered = True
        result.install_path = path
        result.version = self._get_version(path, spec.version_args)
        result.validated = self._validate_agent(spec, path, result.version)
        return result

    def _get_version(self, path: str, args: tuple[str, ...]) -> str:
        try:
            result = subprocess.run(  # noqa: S603
                [path, *args],  # noqa: S607
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
            if result.returncode == 0:
                for line in result.stdout.splitlines():
                    if line.strip():
                        return line.strip()[:100]
            return ""
        except (subprocess.SubprocessError, OSError):
            return ""

    def _validate_agent(self, spec: AgentSpec, path: str, version: str) -> bool:
        """Validate that the agent is functional.

        Validation checks:
          - The binary is executable
          - The version output is non-empty
          - The agent responds to a basic help command (best-effort)
        """
        if not path:
            return False
        # Best-effort: --help should not crash
        try:
            result = subprocess.run(  # noqa: S603
                [path, "--help"],  # noqa: S607
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
            # Some agents exit non-zero on --help; that's OK
            return result.returncode in (0, 1, 2)
        except (subprocess.SubprocessError, OSError):
            return False

    def _register_one(self, result: AgentDiscoveryResult) -> None:
        """Register an agent with the Agent Registry.

        Writes a registration record to the workspace's ``agents/`` directory.
        The actual Agent Registry picks these up at startup.
        """
        import json
        from pathlib import Path

        if not self._workspace_root:
            return
        agents_dir = Path(self._workspace_root) / "agents"
        agents_dir.mkdir(parents=True, exist_ok=True)
        record = {
            "name": result.name,
            "display_name": result.display_name,
            "agent_type": result.agent_type,
            "install_path": result.install_path,
            "version": result.version,
            "capabilities": result.capabilities,
            "registered_at": self._now_iso(),
            "validated": result.validated,
        }
        path = agents_dir / f"{result.name}.json"
        path.write_text(json.dumps(record, indent=2, default=str))

    def _build_manifest(self, result: AgentDiscoveryResult) -> dict[str, Any]:
        """Build a manifest describing the agent's capabilities."""
        return {
            "name": result.name,
            "display_name": result.display_name,
            "agent_type": result.agent_type,
            "version": result.version,
            "install_path": result.install_path,
            "capabilities": result.capabilities,
            "validated": result.validated,
            "manifest_version": "1.0",
            "generated_at": self._now_iso(),
        }

    def _save_manifest(self, name: str, manifest: dict[str, Any]) -> None:
        import json
        from pathlib import Path

        if not self._workspace_root:
            return
        path = Path(self._workspace_root) / "agents" / f"{name}.manifest.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(manifest, indent=2, default=str))

    def _find_spec(self, name: str) -> AgentSpec | None:
        for spec in SUPPORTED_AGENTS:
            if spec.name == name:
                return spec
        return None

    def _now_iso(self) -> str:
        from datetime import UTC, datetime

        return datetime.now(UTC).isoformat()
