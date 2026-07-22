"""AAiOS v5.3 — Enterprise Research & Reasoning Platform.

Models for the Research Engine: ResearchProject, ResearchSession,
ResearchPlan, ResearchTask, ResearchPipeline, ResearchFinding, plus
the multi-agent / multi-model / evidence-graph / verification /
synthesis data structures.

All models are immutable dataclasses with to_dict() for JSON serialization.
Every finding, claim, and conclusion carries evidence, confidence, and
explainability metadata.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4

__all__ = [
    "Claim",
    "ClaimRelation",
    "ClaimRelationType",
    "DocumentSummary",
    "Entity",
    "EvidenceNode",
    "EvidenceRelation",
    "EvidenceRelationType",
    "Fact",
    "FactVerificationReport",
    "KnowledgeSynthesis",
    "MinorityOpinion",
    "ModelAnalysis",
    "ModelReasoningResult",
    "ResearchAgentFinding",
    "ResearchAgentType",
    "ResearchFinding",
    "ResearchMemory",
    "ResearchPlan",
    "ResearchPipeline",
    "ResearchPipelineStage",
    "ResearchProject",
    "ResearchSession",
    "ResearchTask",
    "ResearchTemplate",
    "ResearchTimelineEntry",
    "ResearchWorkspace",
    "Source",
    "SourceReliability",
    "SynthesisSection",
    "VerificationStatus",
]


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class ResearchAgentType(StrEnum):
    """The ten specialized research agent types."""

    LITERATURE = "literature"
    SCIENTIFIC = "scientific"
    LEGAL = "legal"
    BUSINESS = "business"
    TECHNOLOGY = "technology"
    MARKET = "market"
    NEWS = "news"
    FINANCIAL = "financial"
    POLICY = "policy"
    OPEN_DATA = "open_data"


class VerificationStatus(StrEnum):
    """Fact verification status."""

    UNVERIFIED = "unverified"
    VERIFIED = "verified"
    PARTIALLY_VERIFIED = "partially_verified"
    CONTRADICTED = "contradicted"
    UNVERIFIABLE = "unverifiable"


class ClaimRelationType(StrEnum):
    """Relationship types between claims in the evidence graph."""

    SUPPORTS = "supports"
    CONTRADICTS = "contradicts"
    DEPENDS_ON = "depends_on"
    REFERENCES = "references"
    CITES = "cites"
    DERIVED_FROM = "derived_from"


class EvidenceRelationType(StrEnum):
    """Edge types in the evidence graph."""

    SUPPORT = "support"
    CONTRADICTION = "contradiction"
    DEPENDENCY = "dependency"
    REFERENCE = "reference"
    CITATION = "citation"


class SourceReliability(StrEnum):
    """Source reliability tiers."""

    TIER_1_PEER_REVIEWED = "tier_1_peer_reviewed"
    TIER_2_OFFICIAL = "tier_2_official"
    TIER_3_ESTABLISHED = "tier_3_established"
    TIER_4_COMMUNITY = "tier_4_community"
    TIER_5_UNVERIFIED = "tier_5_unverified"


# ---------------------------------------------------------------------------
# Phase 1 — Research Engine core models
# ---------------------------------------------------------------------------


@dataclass
class ResearchProject:
    """A top-level research project."""

    project_id: str = field(default_factory=lambda: uuid4().hex[:12])
    title: str = ""
    description: str = ""
    objectives: list[str] = field(default_factory=list)
    research_questions: list[str] = field(default_factory=list)
    domain: str = ""  # e.g. "scientific", "legal", "market"
    status: str = "planning"  # planning | active | paused | completed | archived
    owner: str = ""
    collaborators: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    started_at: datetime | None = None
    completed_at: datetime | None = None
    session_count: int = 0
    finding_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "project_id": self.project_id,
            "title": self.title,
            "description": self.description,
            "objectives": list(self.objectives),
            "research_questions": list(self.research_questions),
            "domain": self.domain,
            "status": self.status,
            "owner": self.owner,
            "collaborators": list(self.collaborators),
            "tags": list(self.tags),
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "session_count": self.session_count,
            "finding_count": self.finding_count,
        }


@dataclass
class ResearchSession:
    """A single research session within a project."""

    session_id: str = field(default_factory=lambda: uuid4().hex[:12])
    project_id: str = ""
    title: str = ""
    query: str = ""
    scope: str = ""  # broad | focused | deep_dive
    agent_type: str = ""
    status: str = "pending"  # pending | running | completed | failed
    started_at: datetime | None = None
    completed_at: datetime | None = None
    duration_s: float = 0.0
    finding_count: int = 0
    sources_consulted: int = 0
    models_used: list[str] = field(default_factory=list)
    error: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "project_id": self.project_id,
            "title": self.title,
            "query": self.query,
            "scope": self.scope,
            "agent_type": self.agent_type,
            "status": self.status,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "duration_s": round(self.duration_s, 2),
            "finding_count": self.finding_count,
            "sources_consulted": self.sources_consulted,
            "models_used": list(self.models_used),
            "error": self.error,
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class ResearchPlan:
    """A plan for executing a research project."""

    plan_id: str = field(default_factory=lambda: uuid4().hex[:12])
    project_id: str = ""
    title: str = ""
    description: str = ""
    objectives: list[str] = field(default_factory=list)
    research_questions: list[str] = field(default_factory=list)
    methodology: str = ""
    agent_assignments: dict[str, list[str]] = field(default_factory=dict)
    timeline: list[dict[str, Any]] = field(default_factory=list)
    expected_outputs: list[str] = field(default_factory=list)
    risk_assessment: list[str] = field(default_factory=list)
    confidence: float = 0.5
    reasoning: str = ""
    requires_approval: bool = True
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "project_id": self.project_id,
            "title": self.title,
            "description": self.description,
            "objectives": list(self.objectives),
            "research_questions": list(self.research_questions),
            "methodology": self.methodology,
            "agent_assignments": dict(self.agent_assignments),
            "timeline": list(self.timeline),
            "expected_outputs": list(self.expected_outputs),
            "risk_assessment": list(self.risk_assessment),
            "confidence": round(self.confidence, 4),
            "reasoning": self.reasoning,
            "requires_approval": self.requires_approval,
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class ResearchTask:
    """A single task within a research session."""

    task_id: str = field(default_factory=lambda: uuid4().hex[:8])
    session_id: str = ""
    title: str = ""
    description: str = ""
    agent_type: str = ""
    status: str = "pending"  # pending | running | completed | failed | skipped
    priority: str = "normal"
    dependencies: list[str] = field(default_factory=list)
    estimated_minutes: float = 0.0
    actual_minutes: float = 0.0
    inputs: dict[str, Any] = field(default_factory=dict)
    outputs: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    started_at: datetime | None = None
    completed_at: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "session_id": self.session_id,
            "title": self.title,
            "description": self.description,
            "agent_type": self.agent_type,
            "status": self.status,
            "priority": self.priority,
            "dependencies": list(self.dependencies),
            "estimated_minutes": round(self.estimated_minutes, 2),
            "actual_minutes": round(self.actual_minutes, 2),
            "inputs": dict(self.inputs),
            "outputs": dict(self.outputs),
            "error": self.error,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }


@dataclass
class ResearchPipelineStage:
    """A single stage in a research pipeline."""

    stage_id: str = field(default_factory=lambda: uuid4().hex[:8])
    name: str = ""
    description: str = ""
    agent_type: str = ""
    inputs: list[str] = field(default_factory=list)
    outputs: list[str] = field(default_factory=list)
    depends_on: list[str] = field(default_factory=list)
    status: str = "pending"
    parallel: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "stage_id": self.stage_id,
            "name": self.name,
            "description": self.description,
            "agent_type": self.agent_type,
            "inputs": list(self.inputs),
            "outputs": list(self.outputs),
            "depends_on": list(self.depends_on),
            "status": self.status,
            "parallel": self.parallel,
        }


@dataclass
class ResearchPipeline:
    """A multi-stage research pipeline."""

    pipeline_id: str = field(default_factory=lambda: uuid4().hex[:12])
    project_id: str = ""
    name: str = ""
    description: str = ""
    stages: list[ResearchPipelineStage] = field(default_factory=list)
    status: str = "draft"  # draft | running | completed | failed
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, Any]:
        return {
            "pipeline_id": self.pipeline_id,
            "project_id": self.project_id,
            "name": self.name,
            "description": self.description,
            "stages": [s.to_dict() for s in self.stages],
            "status": self.status,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class ResearchTemplate:
    """A reusable research project template."""

    template_id: str = field(default_factory=lambda: uuid4().hex[:8])
    name: str = ""
    description: str = ""
    domain: str = ""
    objectives: list[str] = field(default_factory=list)
    research_questions: list[str] = field(default_factory=list)
    methodology: str = ""
    recommended_agents: list[str] = field(default_factory=list)
    recommended_pipelines: list[str] = field(default_factory=list)
    expected_duration_hours: float = 0.0
    tags: list[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, Any]:
        return {
            "template_id": self.template_id,
            "name": self.name,
            "description": self.description,
            "domain": self.domain,
            "objectives": list(self.objectives),
            "research_questions": list(self.research_questions),
            "methodology": self.methodology,
            "recommended_agents": list(self.recommended_agents),
            "recommended_pipelines": list(self.recommended_pipelines),
            "expected_duration_hours": round(self.expected_duration_hours, 2),
            "tags": list(self.tags),
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class ResearchMemory:
    """Persistent research memory — what was learned across projects."""

    memory_id: str = field(default_factory=lambda: uuid4().hex[:12])
    project_id: str = ""
    memory_type: str = ""  # finding | lesson | pattern | source | method
    key: str = ""
    value: str = ""
    evidence: list[str] = field(default_factory=list)
    confidence: float = 0.5
    relevance_score: float = 0.5
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    last_accessed_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    access_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "memory_id": self.memory_id,
            "project_id": self.project_id,
            "memory_type": self.memory_type,
            "key": self.key,
            "value": self.value,
            "evidence": list(self.evidence),
            "confidence": round(self.confidence, 4),
            "relevance_score": round(self.relevance_score, 4),
            "created_at": self.created_at.isoformat(),
            "last_accessed_at": self.last_accessed_at.isoformat(),
            "access_count": self.access_count,
        }


@dataclass
class ResearchWorkspace:
    """A workspace grouping related research projects."""

    workspace_id: str = field(default_factory=lambda: uuid4().hex[:12])
    name: str = ""
    description: str = ""
    project_ids: list[str] = field(default_factory=list)
    owner: str = ""
    collaborators: list[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, Any]:
        return {
            "workspace_id": self.workspace_id,
            "name": self.name,
            "description": self.description,
            "project_ids": list(self.project_ids),
            "owner": self.owner,
            "collaborators": list(self.collaborators),
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class ResearchTimelineEntry:
    """A single entry in the research timeline."""

    entry_id: str = field(default_factory=lambda: uuid4().hex[:8])
    project_id: str = ""
    session_id: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    kind: str = "session_started"  # session_started | session_completed | finding_added | claim_made | fact_verified | synthesis_generated | ...
    title: str = ""
    description: str = ""
    actor: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "entry_id": self.entry_id,
            "project_id": self.project_id,
            "session_id": self.session_id,
            "timestamp": self.timestamp.isoformat(),
            "kind": self.kind,
            "title": self.title,
            "description": self.description,
            "actor": self.actor,
            "metadata": dict(self.metadata),
        }


# ---------------------------------------------------------------------------
# Phase 2 — Research agent findings
# ---------------------------------------------------------------------------


@dataclass
class Source:
    """A source consulted during research."""

    source_id: str = field(default_factory=lambda: uuid4().hex[:8])
    title: str = ""
    url: str = ""
    source_type: str = ""  # paper | article | report | database | news | official | book | dataset
    authors: list[str] = field(default_factory=list)
    published_at: datetime | None = None
    accessed_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    reliability: str = SourceReliability.TIER_3_ESTABLISHED.value
    reliability_score: float = 0.5  # 0..1
    citation_count: int = 0
    abstract: str = ""
    doi: str = ""
    isbn: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "title": self.title,
            "url": self.url,
            "source_type": self.source_type,
            "authors": list(self.authors),
            "published_at": self.published_at.isoformat() if self.published_at else None,
            "accessed_at": self.accessed_at.isoformat(),
            "reliability": self.reliability,
            "reliability_score": round(self.reliability_score, 4),
            "citation_count": self.citation_count,
            "abstract": self.abstract,
            "doi": self.doi,
            "isbn": self.isbn,
        }


@dataclass
class ResearchAgentFinding:
    """A finding produced by a specialized research agent."""

    finding_id: str = field(default_factory=lambda: uuid4().hex[:10])
    session_id: str = ""
    agent_type: str = ""
    title: str = ""
    summary: str = ""
    key_points: list[str] = field(default_factory=list)
    evidence: list[str] = field(default_factory=list)
    sources: list[Source] = field(default_factory=list)
    confidence: float = 0.5
    limitations: list[str] = field(default_factory=list)
    follow_up_questions: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, Any]:
        return {
            "finding_id": self.finding_id,
            "session_id": self.session_id,
            "agent_type": self.agent_type,
            "title": self.title,
            "summary": self.summary,
            "key_points": list(self.key_points),
            "evidence": list(self.evidence),
            "sources": [s.to_dict() for s in self.sources],
            "confidence": round(self.confidence, 4),
            "limitations": list(self.limitations),
            "follow_up_questions": list(self.follow_up_questions),
            "metadata": dict(self.metadata),
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class ResearchFinding:
    """A consolidated research finding from one or more agents."""

    finding_id: str = field(default_factory=lambda: uuid4().hex[:10])
    project_id: str = ""
    session_id: str = ""
    title: str = ""
    description: str = ""
    agent_findings: list[ResearchAgentFinding] = field(default_factory=list)
    claims: list[str] = field(default_factory=list)
    sources: list[Source] = field(default_factory=list)
    confidence: float = 0.5
    evidence: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, Any]:
        return {
            "finding_id": self.finding_id,
            "project_id": self.project_id,
            "session_id": self.session_id,
            "title": self.title,
            "description": self.description,
            "agent_findings": [f.to_dict() for f in self.agent_findings],
            "claims": list(self.claims),
            "sources": [s.to_dict() for s in self.sources],
            "confidence": round(self.confidence, 4),
            "evidence": list(self.evidence),
            "tags": list(self.tags),
            "created_at": self.created_at.isoformat(),
        }


# ---------------------------------------------------------------------------
# Phase 3 — Multi-model reasoning
# ---------------------------------------------------------------------------


@dataclass
class ModelAnalysis:
    """An independent analysis from a single model."""

    analysis_id: str = field(default_factory=lambda: uuid4().hex[:8])
    model: str = ""
    provider: str = ""
    prompt: str = ""
    response: str = ""
    reasoning: str = ""
    claims: list[str] = field(default_factory=list)
    confidence: float = 0.5
    duration_s: float = 0.0
    token_count: int = 0
    error: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, Any]:
        return {
            "analysis_id": self.analysis_id,
            "model": self.model,
            "provider": self.provider,
            "prompt": self.prompt,
            "response": self.response,
            "reasoning": self.reasoning,
            "claims": list(self.claims),
            "confidence": round(self.confidence, 4),
            "duration_s": round(self.duration_s, 2),
            "token_count": self.token_count,
            "error": self.error,
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class MinorityOpinion:
    """A dissenting opinion in multi-model reasoning."""

    opinion_id: str = field(default_factory=lambda: uuid4().hex[:8])
    model: str = ""
    provider: str = ""
    claim: str = ""
    rationale: str = ""
    evidence: list[str] = field(default_factory=list)
    confidence: float = 0.5
    disagreement_reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "opinion_id": self.opinion_id,
            "model": self.model,
            "provider": self.provider,
            "claim": self.claim,
            "rationale": self.rationale,
            "evidence": list(self.evidence),
            "confidence": round(self.confidence, 4),
            "disagreement_reason": self.disagreement_reason,
        }


@dataclass
class ModelReasoningResult:
    """The result of multi-model reasoning on a single question."""

    result_id: str = field(default_factory=lambda: uuid4().hex[:10])
    question: str = ""
    analyses: list[ModelAnalysis] = field(default_factory=list)
    consensus: str = ""
    consensus_confidence: float = 0.0
    conflicts: list[dict[str, Any]] = field(default_factory=list)
    minority_opinions: list[MinorityOpinion] = field(default_factory=list)
    evidence_ranking: list[dict[str, Any]] = field(default_factory=list)
    explanation: str = ""
    requires_approval: bool = True
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, Any]:
        return {
            "result_id": self.result_id,
            "question": self.question,
            "analyses": [a.to_dict() for a in self.analyses],
            "consensus": self.consensus,
            "consensus_confidence": round(self.consensus_confidence, 4),
            "conflicts": list(self.conflicts),
            "minority_opinions": [o.to_dict() for o in self.minority_opinions],
            "evidence_ranking": list(self.evidence_ranking),
            "explanation": self.explanation,
            "requires_approval": self.requires_approval,
            "created_at": self.created_at.isoformat(),
        }


# ---------------------------------------------------------------------------
# Phase 4 — Evidence graph
# ---------------------------------------------------------------------------


@dataclass
class Claim:
    """A claim made during research."""

    claim_id: str = field(default_factory=lambda: uuid4().hex[:10])
    text: str = ""
    claim_type: str = "factual"  # factual | hypothesis | opinion | prediction | definition
    confidence: float = 0.5
    evidence: list[str] = field(default_factory=list)
    sources: list[str] = field(default_factory=list)  # source_ids
    project_id: str = ""
    session_id: str = ""
    agent_type: str = ""
    model: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    verified: bool = False
    verification_status: str = VerificationStatus.UNVERIFIED.value

    def to_dict(self) -> dict[str, Any]:
        return {
            "claim_id": self.claim_id,
            "text": self.text,
            "claim_type": self.claim_type,
            "confidence": round(self.confidence, 4),
            "evidence": list(self.evidence),
            "sources": list(self.sources),
            "project_id": self.project_id,
            "session_id": self.session_id,
            "agent_type": self.agent_type,
            "model": self.model,
            "created_at": self.created_at.isoformat(),
            "verified": self.verified,
            "verification_status": self.verification_status,
        }


@dataclass
class Fact:
    """A verified fact in the evidence graph."""

    fact_id: str = field(default_factory=lambda: uuid4().hex[:10])
    text: str = ""
    verified: bool = False
    verification_status: str = VerificationStatus.UNVERIFIED.value
    confidence: float = 0.0
    evidence: list[str] = field(default_factory=list)
    sources: list[str] = field(default_factory=list)
    verified_at: datetime | None = None
    verifier: str = ""
    project_id: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, Any]:
        return {
            "fact_id": self.fact_id,
            "text": self.text,
            "verified": self.verified,
            "verification_status": self.verification_status,
            "confidence": round(self.confidence, 4),
            "evidence": list(self.evidence),
            "sources": list(self.sources),
            "verified_at": self.verified_at.isoformat() if self.verified_at else None,
            "verifier": self.verifier,
            "project_id": self.project_id,
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class EvidenceNode:
    """A node in the evidence graph.

    Node kinds: claim, fact, source, document, report, session.
    """

    node_id: str = field(default_factory=lambda: uuid4().hex[:10])
    kind: str = "claim"  # claim | fact | source | document | report | session
    ref_id: str = ""  # ID of the referenced entity
    label: str = ""
    weight: float = 1.0  # evidence strength (0..1)
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "kind": self.kind,
            "ref_id": self.ref_id,
            "label": self.label,
            "weight": round(self.weight, 4),
            "metadata": dict(self.metadata),
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class EvidenceRelation:
    """An edge in the evidence graph."""

    edge_id: str = field(default_factory=lambda: uuid4().hex[:10])
    source_node_id: str = ""
    target_node_id: str = ""
    relation_type: str = EvidenceRelationType.SUPPORT.value
    weight: float = 0.5  # strength of the relationship (0..1)
    evidence: list[str] = field(default_factory=list)
    explanation: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, Any]:
        return {
            "edge_id": self.edge_id,
            "source_node_id": self.source_node_id,
            "target_node_id": self.target_node_id,
            "relation_type": self.relation_type,
            "weight": round(self.weight, 4),
            "evidence": list(self.evidence),
            "explanation": self.explanation,
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class ClaimRelation:
    """A direct claim-to-claim relationship (convenience wrapper)."""

    relation_id: str = field(default_factory=lambda: uuid4().hex[:8])
    source_claim_id: str = ""
    target_claim_id: str = ""
    relation_type: str = ClaimRelationType.SUPPORTS.value
    weight: float = 0.5
    explanation: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "relation_id": self.relation_id,
            "source_claim_id": self.source_claim_id,
            "target_claim_id": self.target_claim_id,
            "relation_type": self.relation_type,
            "weight": round(self.weight, 4),
            "explanation": self.explanation,
        }


# ---------------------------------------------------------------------------
# Phase 5 — Fact verification
# ---------------------------------------------------------------------------


@dataclass
class FactVerificationReport:
    """A complete fact verification report."""

    report_id: str = field(default_factory=lambda: uuid4().hex[:12])
    fact_text: str = ""
    status: str = VerificationStatus.UNVERIFIED.value
    confidence: float = 0.0
    sources_checked: int = 0
    sources_supporting: int = 0
    sources_contradicting: int = 0
    sources_neutral: int = 0
    source_ranking: list[dict[str, Any]] = field(default_factory=list)
    conflicts: list[dict[str, Any]] = field(default_factory=list)
    explanation: str = ""
    verified_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    requires_approval: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "report_id": self.report_id,
            "fact_text": self.fact_text,
            "status": self.status,
            "confidence": round(self.confidence, 4),
            "sources_checked": self.sources_checked,
            "sources_supporting": self.sources_supporting,
            "sources_contradicting": self.sources_contradicting,
            "sources_neutral": self.sources_neutral,
            "source_ranking": list(self.source_ranking),
            "conflicts": list(self.conflicts),
            "explanation": self.explanation,
            "verified_at": self.verified_at.isoformat(),
            "requires_approval": self.requires_approval,
        }


# ---------------------------------------------------------------------------
# Phase 6 — Knowledge synthesis
# ---------------------------------------------------------------------------


@dataclass
class Entity:
    """An entity extracted from research documents."""

    entity_id: str = field(default_factory=lambda: uuid4().hex[:8])
    name: str = ""
    entity_type: str = (
        ""  # person | organization | location | date | concept | event | product | law | metric
    )
    mentions: int = 0
    aliases: list[str] = field(default_factory=list)
    description: str = ""
    confidence: float = 0.5
    sources: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "entity_id": self.entity_id,
            "name": self.name,
            "entity_type": self.entity_type,
            "mentions": self.mentions,
            "aliases": list(self.aliases),
            "description": self.description,
            "confidence": round(self.confidence, 4),
            "sources": list(self.sources),
        }


@dataclass
class SynthesisSection:
    """A section in a knowledge synthesis report."""

    section_id: str = field(default_factory=lambda: uuid4().hex[:8])
    title: str = ""
    section_type: str = ""  # executive_summary | technical_summary | timeline | entities | relationships | decision_support | insights | recommendations | open_questions
    content: str = ""
    bullet_points: list[str] = field(default_factory=list)
    evidence: list[str] = field(default_factory=list)
    confidence: float = 0.5
    sources: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "section_id": self.section_id,
            "title": self.title,
            "section_type": self.section_type,
            "content": self.content,
            "bullet_points": list(self.bullet_points),
            "evidence": list(self.evidence),
            "confidence": round(self.confidence, 4),
            "sources": list(self.sources),
        }


@dataclass
class DocumentSummary:
    """A summary of a single document used in synthesis."""

    doc_id: str = field(default_factory=lambda: uuid4().hex[:8])
    source_id: str = ""
    title: str = ""
    summary: str = ""
    key_points: list[str] = field(default_factory=list)
    relevance: float = 0.5
    word_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "doc_id": self.doc_id,
            "source_id": self.source_id,
            "title": self.title,
            "summary": self.summary,
            "key_points": list(self.key_points),
            "relevance": round(self.relevance, 4),
            "word_count": self.word_count,
        }


@dataclass
class KnowledgeSynthesis:
    """The unified knowledge synthesis from multiple documents."""

    synthesis_id: str = field(default_factory=lambda: uuid4().hex[:12])
    project_id: str = ""
    title: str = ""
    description: str = ""
    sections: list[SynthesisSection] = field(default_factory=list)
    document_summaries: list[DocumentSummary] = field(default_factory=list)
    entities: list[Entity] = field(default_factory=list)
    timeline: list[dict[str, Any]] = field(default_factory=list)
    relationship_map: list[dict[str, Any]] = field(default_factory=list)
    overall_confidence: float = 0.0
    requires_approval: bool = True
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, Any]:
        return {
            "synthesis_id": self.synthesis_id,
            "project_id": self.project_id,
            "title": self.title,
            "description": self.description,
            "sections": [s.to_dict() for s in self.sections],
            "document_summaries": [d.to_dict() for d in self.document_summaries],
            "entities": [e.to_dict() for e in self.entities],
            "timeline": list(self.timeline),
            "relationship_map": list(self.relationship_map),
            "overall_confidence": round(self.overall_confidence, 4),
            "requires_approval": self.requires_approval,
            "created_at": self.created_at.isoformat(),
        }
