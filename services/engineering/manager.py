"""Engineering Intelligence Manager — top-level facade for v5.2 Part 1A.

Wires together:
  - RepositoryIntelligenceEngine (discovery, analysis, issues)
  - CodeIntelligenceEngine (AST analysis, metrics)
  - ArchitectureIntelligenceEngine (layer violations, circular deps, recommendations)
  - EngineeringAgentOrganization (16 specialized agents)
  - CapabilityRegistry (languages, frameworks, domains)
  - EngineeringWorkspaceManager (repository sessions)
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from core.logging import get_logger
from services.engineering.agents import (
    CapabilityRegistry,
    EngineeringAgentOrganization,
    EngineeringWorkspaceManager,
)
from services.engineering.models import (
    EngCapability,
)
from services.engineering.repository_engine import (
    ArchitectureIntelligenceEngine,
    CodeIntelligenceEngine,
    RepositoryIntelligenceEngine,
)

_log = get_logger(__name__)

__all__ = ["EngineeringManager"]


class EngineeringManager:
    """Top-level facade for the Autonomous Software Engineering Platform.

    Usage:
        mgr = EngineeringManager(repo_root=Path("."))
        analysis = await mgr.analyze_repository()
        recs = await mgr.architecture_recommendations()
        agents = mgr.list_engineering_agents()
    """

    def __init__(self, repo_root: Path | str = ".") -> None:
        self._root = Path(repo_root)
        self.repo_intelligence = RepositoryIntelligenceEngine(self._root)
        self.code_intelligence = CodeIntelligenceEngine()
        self.architecture = ArchitectureIntelligenceEngine(self._root)
        self.agents = EngineeringAgentOrganization()
        self.capabilities = CapabilityRegistry()
        self.workspaces = EngineeringWorkspaceManager()

    # --- Repository Intelligence ---

    async def discover_repositories(self) -> list[dict[str, Any]]:
        repos = await self.repo_intelligence.discover_repositories()
        return [r.to_dict() for r in repos]

    async def analyze_repository(self) -> dict[str, Any]:
        analysis = await self.repo_intelligence.analyze()
        return analysis.to_dict()

    async def analyze_file(self, file_path: str) -> dict[str, Any]:
        analysis = await self.code_intelligence.analyze_file(Path(file_path))
        return analysis.to_dict()

    # --- Architecture Intelligence ---

    async def architecture_recommendations(self) -> list[dict[str, Any]]:
        recs = await self.architecture.inspect()
        return [r.to_dict() for r in recs]

    # --- Engineering Agents ---

    def list_engineering_agents(self) -> list[dict[str, Any]]:
        return [a.to_dict() for a in self.agents.list_agents()]

    def get_engineering_agent(self, agent_id: str) -> dict[str, Any] | None:
        agent = self.agents.get_agent(agent_id)
        return agent.to_dict() if agent else None

    def select_agent_for_task(
        self,
        *,
        language: str | None = None,
        framework: str | None = None,
        agent_type: str | None = None,
    ) -> dict[str, Any] | None:
        agent = self.agents.select_for_task(
            language=language, framework=framework, agent_type=agent_type,
        )
        return agent.to_dict() if agent else None

    # --- Capability Registry ---

    async def register_capability(self, capability: EngCapability) -> dict[str, Any]:
        cap = await self.capabilities.register(capability)
        return cap.to_dict()

    async def list_capabilities(self) -> list[dict[str, Any]]:
        caps = await self.capabilities.list_all()
        return [c.to_dict() for c in caps]

    async def capability_stats(self) -> dict[str, Any]:
        return await self.capabilities.stats()

    # --- Engineering Workspace ---

    async def create_workspace(self, name: str, repo_paths: list[str]) -> dict[str, Any]:
        ws = await self.workspaces.create_workspace(name, repo_paths)
        return ws.to_dict()

    async def list_workspaces(self) -> list[dict[str, Any]]:
        workspaces = await self.workspaces.list_workspaces()
        return [w.to_dict() for w in workspaces]

    async def create_workspace_session(
        self,
        workspace_id: str,
        repo_path: str,
        branch: str = "main",
        mission_id: str | None = None,
    ) -> dict[str, Any] | None:
        session = await self.workspaces.create_session(
            workspace_id, repo_path, branch, mission_id,
        )
        return session.to_dict() if session else None

    # --- Summary ---

    async def get_overview(self) -> dict[str, Any]:
        """Get engineering overview."""
        analysis = await self.repo_intelligence.analyze()
        recs = await self.architecture.inspect()
        return {
            "repository": analysis.to_dict(),
            "architecture_recommendations": len(recs),
            "engineering_agents": len(self.agents.list_agents()),
            "capabilities": await self.capabilities.stats(),
            "workspaces": len(await self.workspaces.list_workspaces()),
        }
