"""Engineering Intelligence Manager — top-level facade for v5.2.

Wires together:
  - RepositoryIntelligenceEngine (discovery, analysis, issues)
  - CodeIntelligenceEngine (AST analysis, metrics)
  - ArchitectureIntelligenceEngine (layer violations, circular deps, recommendations)
  - EngineeringAgentOrganization (16 specialized agents)
  - CapabilityRegistry (languages, frameworks, domains)
  - EngineeringWorkspaceManager (repository sessions)
  - EngineeringReviewEngine (12 review types) [Phase 17]
  - TestIntelligenceEngine [Phase 18]
  - DocumentationIntelligenceEngine [Phase 19]
  - RepositoryEvolutionEngine [Phase 20]
  - ReleaseReadinessEngine [Phase 21]
  - DeveloperProductivityEngine [Phase 22]
  - RepositoryHealthCenter [Phase 23]
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
from services.engineering.documentation_intelligence import (
    DocumentationIntelligenceEngine,
)
from services.engineering.evolution_engine import RepositoryEvolutionEngine
from services.engineering.health_center import RepositoryHealthCenter
from services.engineering.models import (
    EngCapability,
)
from services.engineering.productivity_engine import DeveloperProductivityEngine
from services.engineering.release_readiness import ReleaseReadinessEngine
from services.engineering.repository_engine import (
    ArchitectureIntelligenceEngine,
    CodeIntelligenceEngine,
    RepositoryIntelligenceEngine,
)
from services.engineering.review_engine import EngineeringReviewEngine, ReviewType
from services.engineering.test_intelligence import TestIntelligenceEngine

_log = get_logger(__name__)

__all__ = ["EngineeringManager"]


class EngineeringManager:
    """Top-level facade for the Autonomous Software Engineering Platform.

    Usage:
        mgr = EngineeringManager(repo_root=Path("."))
        analysis = await mgr.analyze_repository()
        recs = await mgr.architecture_recommendations()
        review = await mgr.review("code", ".")
        health = await mgr.health()
        readiness = await mgr.release_readiness(version="5.2.0")
    """

    def __init__(self, repo_root: Path | str = ".") -> None:
        self._root = Path(repo_root)
        # Phase 1A engines
        self.repo_intelligence = RepositoryIntelligenceEngine(self._root)
        self.code_intelligence = CodeIntelligenceEngine()
        self.architecture = ArchitectureIntelligenceEngine(self._root)
        self.agents = EngineeringAgentOrganization()
        self.capabilities = CapabilityRegistry()
        self.workspaces = EngineeringWorkspaceManager()
        # Phase 1B-2 engines
        self.review_engine = EngineeringReviewEngine()
        self.test_intelligence = TestIntelligenceEngine()
        self.documentation = DocumentationIntelligenceEngine()
        self.evolution = RepositoryEvolutionEngine(self._root)
        self.release_readiness_engine = ReleaseReadinessEngine()
        self.productivity = DeveloperProductivityEngine()
        self.health_center = RepositoryHealthCenter(self._root)

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

    # --- Engineering Review (Phase 17) ---

    async def review(
        self,
        review_type: ReviewType | str,
        target: str | Path,
        *,
        history: list[Any] | None = None,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        report = await self.review_engine.review(review_type, target, history=history, context=context)
        return report.to_dict()

    async def review_all(
        self,
        target: str | Path,
        *,
        history: list[Any] | None = None,
    ) -> dict[str, Any]:
        results = await self.review_engine.review_all(target, history=history)
        return {k: v.to_dict() for k, v in results.items()}

    # --- Test Intelligence (Phase 18) ---

    async def test_suite_analysis(self) -> dict[str, Any]:
        report = await self.test_intelligence.analyze_suite(self._root / "tests")
        return report.to_dict()

    async def test_coverage(self) -> dict[str, Any]:
        report = await self.test_intelligence.coverage_report(self._root)
        return report.to_dict()

    async def test_risk(self, *, recent_failures: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        report = await self.test_intelligence.risk_report(self._root, recent_failures=recent_failures)
        return report.to_dict()

    # --- Documentation Intelligence (Phase 19) ---

    async def documentation_analysis(self) -> dict[str, Any]:
        report = await self.documentation.analyze(self._root)
        return report.to_dict()

    async def documentation_recommendations(self) -> list[dict[str, Any]]:
        return await self.documentation.recommendations(self._root)

    # --- Repository Evolution (Phase 20) ---

    async def evolution_timeline(self, limit: int = 100) -> list[dict[str, Any]]:
        timeline = await self.evolution.timeline(limit=limit)
        return [t.to_dict() for t in timeline]

    async def evolution_dashboard(self) -> dict[str, Any]:
        dash = await self.evolution.dashboard()
        return dash.to_dict()

    async def evolution_report(self) -> dict[str, Any]:
        report = await self.evolution.report()
        return report.to_dict()

    # --- Release Readiness (Phase 21) ---

    async def release_readiness(self, *, version: str = "") -> dict[str, Any]:
        report = await self.release_readiness_engine.evaluate(self._root, version=version)
        return report.to_dict()

    async def certification_report(self, *, version: str = "") -> dict[str, Any]:
        cert = await self.release_readiness_engine.certification_report(self._root, version=version)
        return cert.to_dict()

    # --- Developer Productivity (Phase 22) ---

    def record_productivity_event(self, event: dict[str, Any]) -> None:
        self.productivity.record_event(event)

    async def productivity_metrics(self) -> dict[str, Any]:
        m = await self.productivity.metrics()
        return m.to_dict()

    async def productivity_dora(self) -> dict[str, Any]:
        d = await self.productivity.dora()
        return d.to_dict()

    async def productivity_dashboard(self) -> dict[str, Any]:
        dash = await self.productivity.dashboard()
        return dash.to_dict()

    async def productivity_report(self) -> dict[str, Any]:
        report = await self.productivity.report()
        return report.to_dict()

    # --- Repository Health Center (Phase 23) ---

    async def health(self) -> dict[str, Any]:
        report = await self.health_center.assess()
        return report.to_dict()

    async def health_quick_score(self) -> float:
        return await self.health_center.quick_score()

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
        """Get engineering overview — aggregates all subsystems."""
        analysis = await self.repo_intelligence.analyze()
        recs = await self.architecture.inspect()
        health = await self.health_center.quick_score()
        return {
            "repository": analysis.to_dict(),
            "architecture_recommendations": len(recs),
            "engineering_agents": len(self.agents.list_agents()),
            "capabilities": await self.capabilities.stats(),
            "workspaces": len(await self.workspaces.list_workspaces()),
            "health_score": round(health, 2),
        }
