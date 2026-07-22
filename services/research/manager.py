"""ResearchManager — top-level facade for v5.3.

Wires together all six phases of the Enterprise Research & Reasoning
Platform:

  - ResearchEngine (Phase 1)
  - ResearchAgentOrganization (Phase 2)
  - MultiModelReasoningEngine (Phase 3)
  - EvidenceGraph (Phase 4)
  - FactVerificationEngine (Phase 5)
  - KnowledgeSynthesisEngine (Phase 6)

The facade provides a single entry point and ensures that every
conclusion carries evidence, confidence, and explainability metadata.
"""

from __future__ import annotations

from typing import Any

from core.logging import get_logger
from services.research.agents import ResearchAgentOrganization
from services.research.engine import ResearchEngine
from services.research.evidence_graph import EvidenceGraph
from services.research.models import (
    Claim,
    Fact,
    FactVerificationReport,
    KnowledgeSynthesis,
    ModelAnalysis,
    ModelReasoningResult,
    ResearchAgentFinding,
    ResearchFinding,
    ResearchPipeline,
    ResearchPlan,
    ResearchProject,
    ResearchSession,
    ResearchTask,
    ResearchTemplate,
    Source,
)
from services.research.multi_model import MultiModelReasoningEngine
from services.research.synthesis import KnowledgeSynthesisEngine
from services.research.verification import FactVerificationEngine

_log = get_logger(__name__)

__all__ = ["ResearchManager"]


class ResearchManager:
    """Top-level facade for the Enterprise Research & Reasoning Platform.

    Usage:
        mgr = ResearchManager()
        project = await mgr.create_project("AI Impact Study", domain="scientific")
        session = await mgr.create_session(project.project_id, "Lit Review", query="...")
        finding = await mgr.research_with_agent("scientific", "What is X?", session_id=session.session_id)
        synthesis = await mgr.synthesize(project.project_id, "Synthesis", documents=[...])
    """

    def __init__(self) -> None:
        self.engine = ResearchEngine()
        self.agents = ResearchAgentOrganization()
        self.multi_model = MultiModelReasoningEngine()
        self.evidence_graph = EvidenceGraph()
        self.verification = FactVerificationEngine()
        self.synthesis = KnowledgeSynthesisEngine()

    # --- Phase 1: Research Engine --------------------------------------

    async def create_project(
        self, title: str, description: str = "", **kwargs: Any
    ) -> ResearchProject:
        return await self.engine.create_project(title, description, **kwargs)

    async def get_project(self, project_id: str) -> ResearchProject | None:
        return await self.engine.get_project(project_id)

    async def list_projects(
        self, *, status: str | None = None, domain: str | None = None
    ) -> list[ResearchProject]:
        return await self.engine.list_projects(status=status, domain=domain)

    async def create_session(
        self,
        project_id: str,
        title: str,
        query: str,
        *,
        scope: str = "focused",
        agent_type: str = "",
    ) -> ResearchSession | None:
        return await self.engine.create_session(
            project_id, title, query, scope=scope, agent_type=agent_type
        )

    async def list_sessions(
        self, *, project_id: str | None = None, status: str | None = None
    ) -> list[ResearchSession]:
        return await self.engine.list_sessions(project_id=project_id, status=status)

    async def create_plan(
        self, project_id: str, title: str, description: str = "", **kwargs: Any
    ) -> ResearchPlan | None:
        return await self.engine.create_plan(project_id, title, description, **kwargs)

    async def create_task(
        self, session_id: str, title: str, description: str = "", **kwargs: Any
    ) -> ResearchTask | None:
        return await self.engine.create_task(session_id, title, description, **kwargs)

    async def create_pipeline(
        self, project_id: str, name: str, description: str = "", **kwargs: Any
    ) -> ResearchPipeline | None:
        return await self.engine.create_pipeline(project_id, name, description, **kwargs)

    async def create_template(
        self, name: str, description: str = "", **kwargs: Any
    ) -> ResearchTemplate:
        return await self.engine.create_template(name, description, **kwargs)

    async def timeline(
        self, *, project_id: str | None = None, limit: int = 100
    ) -> list[dict[str, Any]]:
        entries = await self.engine.timeline(project_id=project_id, limit=limit)
        return [e.to_dict() for e in entries]

    async def history(self, project_id: str) -> dict[str, Any]:
        h = await self.engine.history(project_id)
        return h.to_dict()

    async def stats(self) -> dict[str, Any]:
        return await self.engine.stats()

    # --- Phase 2: Multi-Agent Research ---------------------------------

    def list_research_agents(self) -> list[dict[str, Any]]:
        return self.agents.list_agents()

    def get_research_agent(self, agent_type: str) -> dict[str, Any] | None:
        agent = self.agents.get_agent(agent_type)
        return (
            {
                "agent_type": agent.agent_type.value,
                "display_name": agent.display_name,
                "description": agent.description,
                "default_reliability": agent.default_reliability.value,
            }
            if agent
            else None
        )

    async def research_with_agent(
        self,
        agent_type: str,
        query: str,
        *,
        session_id: str = "",
        source_material: list[dict[str, Any]] | None = None,
        options: dict[str, Any] | None = None,
    ) -> ResearchAgentFinding | None:
        agent = self.agents.get_agent(agent_type)
        if not agent:
            return None
        return await agent.research(
            query, session_id=session_id, source_material=source_material, options=options
        )

    async def research_with_all_agents(
        self,
        query: str,
        *,
        source_material: list[dict[str, Any]] | None = None,
    ) -> list[ResearchAgentFinding]:
        return await self.agents.research_with_all(query, source_material=source_material)

    async def research_with_selected_agent(
        self,
        query: str,
        *,
        session_id: str = "",
        source_material: list[dict[str, Any]] | None = None,
    ) -> ResearchAgentFinding | None:
        """Auto-select the best agent for the query."""
        agent = self.agents.select_for_query(query)
        if not agent:
            return None
        return await agent.research(query, session_id=session_id, source_material=source_material)

    async def add_finding(
        self,
        project_id: str,
        session_id: str,
        title: str,
        description: str = "",
        **kwargs: Any,
    ) -> ResearchFinding | None:
        return await self.engine.add_finding(project_id, session_id, title, description, **kwargs)

    async def list_findings(
        self, *, project_id: str | None = None, session_id: str | None = None
    ) -> list[ResearchFinding]:
        return await self.engine.list_findings(project_id=project_id, session_id=session_id)

    # --- Phase 3: Multi-Model Reasoning --------------------------------

    async def reason(
        self,
        question: str,
        analyses: list[ModelAnalysis],
        *,
        min_models_for_consensus: int = 2,
    ) -> ModelReasoningResult:
        return await self.multi_model.reason(
            question, analyses, min_models_for_consensus=min_models_for_consensus
        )

    # --- Phase 4: Evidence Graph ---------------------------------------

    def add_claim_to_graph(self, claim: Claim) -> dict[str, Any]:
        node = self.evidence_graph.add_claim(claim)
        return node.to_dict()

    def add_fact_to_graph(self, fact: Fact) -> dict[str, Any]:
        node = self.evidence_graph.add_fact(fact)
        return node.to_dict()

    def add_source_to_graph(self, source: Source) -> dict[str, Any]:
        node = self.evidence_graph.add_source(source)
        return node.to_dict()

    def evidence_graph_stats(self) -> dict[str, Any]:
        return self.evidence_graph.stats()

    def evidence_graph_search(
        self, query: str, kinds: list[str] | None = None
    ) -> list[dict[str, Any]]:
        nodes = self.evidence_graph.search(query, kinds=kinds)
        return [n.to_dict() for n in nodes]

    # --- Phase 5: Fact Verification ------------------------------------

    async def verify_fact(self, fact_text: str, sources: list[Source]) -> FactVerificationReport:
        return await self.verification.verify(fact_text, sources)

    async def verify_claim(
        self, claim: Claim, sources: list[Source]
    ) -> tuple[Fact, FactVerificationReport]:
        return await self.verification.verify_claim(claim, sources)

    # --- Phase 6: Knowledge Synthesis ----------------------------------

    async def synthesize(
        self,
        project_id: str,
        title: str,
        documents: list[Source],
        *,
        description: str = "",
        research_question: str = "",
    ) -> KnowledgeSynthesis:
        return await self.synthesis.synthesize(
            project_id,
            title,
            documents,
            description=description,
            research_question=research_question,
        )

    # --- Overview -------------------------------------------------------

    async def get_overview(self) -> dict[str, Any]:
        """Get a research platform overview."""
        stats = await self.engine.stats()
        return {
            "engine_stats": stats,
            "research_agents": len(self.agents.list_agents()),
            "evidence_graph": self.evidence_graph.stats(),
        }
