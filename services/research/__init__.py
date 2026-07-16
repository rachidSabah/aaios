"""AAiOS v5.3 — Enterprise Research & Reasoning Platform.

A research operating system that gathers information, verifies facts,
compares sources, detects contradictions, reasons across multiple models,
builds knowledge, and explains every conclusion.

Modules:
  - models: ResearchProject, ResearchSession, ResearchPlan, ResearchTask,
    ResearchPipeline, ResearchTemplate, ResearchMemory, ResearchWorkspace,
    ResearchTimelineEntry, ResearchFinding, ResearchAgentFinding,
    ModelAnalysis, ModelReasoningResult, MinorityOpinion, Claim, Fact,
    EvidenceNode, EvidenceRelation, FactVerificationReport,
    KnowledgeSynthesis, SynthesisSection, Entity, DocumentSummary, Source.
  - engine: ResearchEngine (Phase 1) — projects, sessions, plans, tasks,
    pipelines, templates, memory, workspaces, timeline, history.
  - agents: 10 specialized research agents (Phase 2) and
    ResearchAgentOrganization.
  - multi_model: MultiModelReasoningEngine (Phase 3).
  - evidence_graph: EvidenceGraph (Phase 4).
  - verification: FactVerificationEngine (Phase 5).
  - synthesis: KnowledgeSynthesisEngine (Phase 6).
  - manager: ResearchManager facade.

Design Principles:
  - Every conclusion contains evidence.
  - Every claim has a confidence score.
  - Every export requires human approval.
  - No intentional hallucination — when evidence is missing, the engine
    says so explicitly and produces low-confidence output.
  - All services are read-only with respect to external systems; they
    never publish or modify production data.
"""

from __future__ import annotations

from services.research.agents import (
    BusinessResearchAgent,
    FinancialResearchAgent,
    LegalResearchAgent,
    LiteratureAgent,
    MarketResearchAgent,
    NewsResearchAgent,
    OpenDataResearchAgent,
    PolicyResearchAgent,
    ResearchAgentBase,
    ResearchAgentOrganization,
    ScientificResearchAgent,
    TechnologyResearchAgent,
)
from services.research.engine import ResearchEngine, ResearchHistory
from services.research.evidence_graph import EvidenceGraph
from services.research.manager import ResearchManager
from services.research.models import (
    Claim,
    ClaimRelation,
    ClaimRelationType,
    DocumentSummary,
    Entity,
    EvidenceNode,
    EvidenceRelation,
    EvidenceRelationType,
    Fact,
    FactVerificationReport,
    KnowledgeSynthesis,
    MinorityOpinion,
    ModelAnalysis,
    ModelReasoningResult,
    ResearchAgentFinding,
    ResearchAgentType,
    ResearchFinding,
    ResearchMemory,
    ResearchPipeline,
    ResearchPipelineStage,
    ResearchPlan,
    ResearchProject,
    ResearchSession,
    ResearchTask,
    ResearchTemplate,
    ResearchTimelineEntry,
    ResearchWorkspace,
    Source,
    SourceReliability,
    SynthesisSection,
    VerificationStatus,
)
from services.research.multi_model import MultiModelReasoningEngine
from services.research.synthesis import KnowledgeSynthesisEngine
from services.research.verification import FactVerificationEngine

__all__ = [
    "BusinessResearchAgent",
    "Claim",
    "ClaimRelation",
    "ClaimRelationType",
    "DocumentSummary",
    "Entity",
    "EvidenceGraph",
    "EvidenceNode",
    "EvidenceRelation",
    "EvidenceRelationType",
    "Fact",
    "FactVerificationEngine",
    "FactVerificationReport",
    "FinancialResearchAgent",
    "KnowledgeSynthesis",
    "KnowledgeSynthesisEngine",
    "LegalResearchAgent",
    "LiteratureAgent",
    "MarketResearchAgent",
    "MinorityOpinion",
    "ModelAnalysis",
    "ModelReasoningResult",
    "MultiModelReasoningEngine",
    "NewsResearchAgent",
    "OpenDataResearchAgent",
    "PolicyResearchAgent",
    "ResearchAgentBase",
    "ResearchAgentFinding",
    "ResearchAgentOrganization",
    "ResearchAgentType",
    "ResearchEngine",
    "ResearchFinding",
    "ResearchHistory",
    "ResearchManager",
    "ResearchMemory",
    "ResearchPipeline",
    "ResearchPipelineStage",
    "ResearchPlan",
    "ResearchProject",
    "ResearchSession",
    "ResearchTask",
    "ResearchTemplate",
    "ResearchTimelineEntry",
    "ResearchWorkspace",
    "ScientificResearchAgent",
    "Source",
    "SourceReliability",
    "SynthesisSection",
    "TechnologyResearchAgent",
    "VerificationStatus",
]
