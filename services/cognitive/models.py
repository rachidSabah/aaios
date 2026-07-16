"""Cognitive Intelligence models — predictions, recommendations, knowledge graph nodes.

All models are immutable dataclasses with to_dict() for JSON serialization.
Every prediction includes an explanation field for explainability.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4

__all__ = [
    "ArchIssue",
    "ArchIssueType",
    "EnterpriseReport",
    "EnterpriseReportType",
    "GraphNode",
    "GraphEdge",
    "GraphType",
    "KnowledgeGraph",
    "LearningInsight",
    "LearningMetric",
    "PredictionResult",
    "PredictionType",
    "Recommendation",
    "RecommendationStatus",
    "RecommendationType",
]


class PredictionType(StrEnum):
    MISSION_DURATION = "mission_duration"
    SUCCESS_PROBABILITY = "success_probability"
    FAILURE_PROBABILITY = "failure_probability"
    BUDGET = "budget"
    LATENCY = "latency"
    TOKEN_CONSUMPTION = "token_consumption"
    PROVIDER_RELIABILITY = "provider_reliability"
    AGENT_UTILIZATION = "agent_utilization"
    MEMORY_REQUIREMENT = "memory_requirement"
    CPU_REQUIREMENT = "cpu_requirement"
    RISK_SCORE = "risk_score"
    CONFIDENCE_SCORE = "confidence_score"


class RecommendationType(StrEnum):
    ALTERNATIVE_PROVIDER = "alternative_provider"
    ALTERNATIVE_AGENT = "alternative_agent"
    WORKFLOW_RESTRUCTURING = "workflow_restructuring"
    PARALLEL_EXECUTION = "parallel_execution"
    BUDGET_OPTIMIZATION = "budget_optimization"
    RETRY_OPTIMIZATION = "retry_optimization"
    CONTEXT_OPTIMIZATION = "context_optimization"
    MEMORY_OPTIMIZATION = "memory_optimization"
    ROUTING_OPTIMIZATION = "routing_optimization"


class RecommendationStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    APPLIED = "applied"


class GraphType(StrEnum):
    AGENT = "agent"
    PROVIDER = "provider"
    PROJECT = "project"
    FILE = "file"
    USER = "user"
    TASK = "task"
    WORKFLOW = "workflow"
    EXECUTION = "execution"
    PLUGIN = "plugin"
    DOCUMENT = "document"
    REPOSITORY = "repository"
    ERROR = "error"
    FIX = "fix"
    CAPABILITY = "capability"


class ArchIssueType(StrEnum):
    DEAD_CODE = "dead_code"
    DUPLICATE_LOGIC = "duplicate_logic"
    ARCH_DRIFT = "arch_drift"
    CIRCULAR_DEPENDENCY = "circular_dependency"
    PERFORMANCE_BOTTLENECK = "performance_bottleneck"
    SECURITY_WEAKNESS = "security_weakness"
    DOC_GAP = "doc_gap"
    MISSING_TESTS = "missing_tests"
    DEPENDENCY_ISSUE = "dependency_issue"


class EnterpriseReportType(StrEnum):
    ARCHITECTURE = "architecture"
    PERFORMANCE = "performance"
    SECURITY = "security"
    COST = "cost"
    RELIABILITY = "reliability"
    MISSION = "mission"
    EXECUTION = "execution"
    KNOWLEDGE = "knowledge"
    GOVERNANCE = "governance"
    REPOSITORY = "repository"


@dataclass
class PredictionResult:
    """A single prediction with explanation."""

    prediction_id: str = field(default_factory=lambda: uuid4().hex[:12])
    prediction_type: str = PredictionType.SUCCESS_PROBABILITY.value
    target: str = ""
    predicted_value: float = 0.0
    confidence: float = 0.5
    explanation: str = ""
    evidence: dict[str, Any] = field(default_factory=dict)
    recommended_actions: list[str] = field(default_factory=list)
    predicted_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, Any]:
        return {
            "prediction_id": self.prediction_id,
            "prediction_type": self.prediction_type,
            "target": self.target,
            "predicted_value": round(self.predicted_value, 4),
            "confidence": round(self.confidence, 4),
            "explanation": self.explanation,
            "evidence": dict(self.evidence),
            "recommended_actions": list(self.recommended_actions),
            "predicted_at": self.predicted_at.isoformat(),
        }


@dataclass
class Recommendation:
    """An optimization recommendation (never auto-applied)."""

    recommendation_id: str = field(default_factory=lambda: uuid4().hex[:12])
    recommendation_type: str = RecommendationType.ROUTING_OPTIMIZATION.value
    title: str = ""
    description: str = ""
    current_state: str = ""
    recommended_state: str = ""
    expected_improvement: str = ""
    estimated_impact: float = 0.0
    confidence: float = 0.0
    priority: str = "normal"
    affected_components: list[str] = field(default_factory=list)
    evidence: dict[str, Any] = field(default_factory=dict)
    requires_approval: bool = True
    status: str = RecommendationStatus.PENDING.value
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, Any]:
        return {
            "recommendation_id": self.recommendation_id,
            "recommendation_type": self.recommendation_type,
            "title": self.title,
            "description": self.description,
            "current_state": self.current_state,
            "recommended_state": self.recommended_state,
            "expected_improvement": self.expected_improvement,
            "estimated_impact": round(self.estimated_impact, 4),
            "confidence": round(self.confidence, 4),
            "priority": self.priority,
            "affected_components": list(self.affected_components),
            "evidence": dict(self.evidence),
            "requires_approval": self.requires_approval,
            "status": self.status,
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class LearningInsight:
    """A learned insight from historical data."""

    insight_id: str = field(default_factory=lambda: uuid4().hex[:12])
    category: str = ""  # best_provider, best_agent, best_workflow, etc.
    finding: str = ""
    evidence: dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.5
    explanation: str = ""
    discovered_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, Any]:
        return {
            "insight_id": self.insight_id,
            "category": self.category,
            "finding": self.finding,
            "evidence": dict(self.evidence),
            "confidence": round(self.confidence, 4),
            "explanation": self.explanation,
            "discovered_at": self.discovered_at.isoformat(),
        }


@dataclass
class LearningMetric:
    """A statistical learning metric."""

    name: str = ""
    value: float = 0.0
    unit: str = ""
    sample_count: int = 0
    explanation: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "value": round(self.value, 4),
            "unit": self.unit,
            "sample_count": self.sample_count,
            "explanation": self.explanation,
        }


@dataclass
class GraphNode:
    """A node in the enterprise knowledge graph."""

    node_id: str = field(default_factory=lambda: uuid4().hex[:12])
    node_type: str = GraphType.AGENT.value
    name: str = ""
    properties: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "node_type": self.node_type,
            "name": self.name,
            "properties": dict(self.properties),
        }


@dataclass
class GraphEdge:
    """An edge in the enterprise knowledge graph."""

    source_id: str = ""
    target_id: str = ""
    relationship: str = ""  # depends_on, executes, produces, fixes, etc.
    properties: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "target_id": self.target_id,
            "relationship": self.relationship,
            "properties": dict(self.properties),
        }


@dataclass
class KnowledgeGraph:
    """The enterprise knowledge graph."""

    nodes: list[GraphNode] = field(default_factory=list)
    edges: list[GraphEdge] = field(default_factory=list)
    built_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, Any]:
        return {
            "nodes": [n.to_dict() for n in self.nodes],
            "edges": [e.to_dict() for e in self.edges],
            "node_count": len(self.nodes),
            "edge_count": len(self.edges),
            "built_at": self.built_at.isoformat(),
        }


@dataclass
class ArchIssue:
    """An architecture issue detected by repository intelligence."""

    issue_id: str = field(default_factory=lambda: uuid4().hex[:12])
    issue_type: str = ArchIssueType.DEAD_CODE.value
    severity: str = "medium"  # low, medium, high, critical
    file: str = ""
    line: int = 0
    description: str = ""
    recommendation: str = ""
    detected_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, Any]:
        return {
            "issue_id": self.issue_id,
            "issue_type": self.issue_type,
            "severity": self.severity,
            "file": self.file,
            "line": self.line,
            "description": self.description,
            "recommendation": self.recommendation,
            "detected_at": self.detected_at.isoformat(),
        }


@dataclass
class EnterpriseReport:
    """An enterprise report."""

    report_id: str = field(default_factory=lambda: uuid4().hex[:12])
    report_type: str = EnterpriseReportType.ARCHITECTURE.value
    generated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    title: str = ""
    summary: str = ""
    key_findings: list[str] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)
    recommendations: list[str] = field(default_factory=list)
    data: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "report_id": self.report_id,
            "report_type": self.report_type,
            "generated_at": self.generated_at.isoformat(),
            "title": self.title,
            "summary": self.summary,
            "key_findings": list(self.key_findings),
            "metrics": dict(self.metrics),
            "recommendations": list(self.recommendations),
            "data": dict(self.data),
        }
