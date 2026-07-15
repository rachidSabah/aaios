"""Intelligence models — health scores, forecasts, recommendations, risks.

All intelligence outputs are immutable dataclasses with to_dict() for
JSON serialization. Every score is 0.0-1.0 unless otherwise noted.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any
from uuid import uuid4

__all__ = [
    "CapacityForecast",
    "ComponentHealth",
    "CostBreakdown",
    "CostForecast",
    "DigitalTwinNode",
    "DigitalTwinSnapshot",
    "EnterpriseHealthScore",
    "ForecastConfidence",
    "ForecastResult",
    "ForecastType",
    "HealthDimension",
    "IntelligenceReport",
    "IntelligenceReportType",
    "OptimizationRecommendation",
    "OptimizationType",
    "OperationalMetrics",
    "RiskAssessment",
    "RiskLevel",
    "RiskType",
]


class HealthDimension(StrEnum):
    """Dimensions of enterprise health."""

    OPERATIONAL = "operational"
    MISSION = "mission"
    AGENT_EFFICIENCY = "agent_efficiency"
    PROVIDER_EFFICIENCY = "provider_efficiency"
    WORKFLOW_QUALITY = "workflow_quality"
    EXECUTION_SUCCESS = "execution_success"
    RISK_LEVEL = "risk_level"
    RELIABILITY = "reliability"
    COST_EFFICIENCY = "cost_efficiency"
    LEARNING_VELOCITY = "learning_velocity"
    INNOVATION = "innovation"


class ForecastType(StrEnum):
    """Types of predictions the system can make."""

    MISSION_FAILURE = "mission_failure"
    WORKFLOW_BOTTLENECK = "workflow_bottleneck"
    PROVIDER_OUTAGE = "provider_outage"
    AGENT_DEGRADATION = "agent_degradation"
    MEMORY_SATURATION = "memory_saturation"
    QUEUE_CONGESTION = "queue_congestion"
    BUDGET_OVERRUN = "budget_overrun"
    DEADLINE_RISK = "deadline_risk"
    RESOURCE_EXHAUSTION = "resource_exhaustion"
    CAPACITY_LIMIT = "capacity_limit"


class ForecastConfidence(StrEnum):
    """Confidence levels for forecasts."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class OptimizationType(StrEnum):
    """Types of optimization recommendations."""

    ROUTING = "routing"
    PROVIDER_SELECTION = "provider_selection"
    AGENT_ASSIGNMENT = "agent_assignment"
    WORKFLOW = "workflow"
    PROMPT = "prompt"
    SCHEDULING = "scheduling"
    CONCURRENCY = "concurrency"
    RETRY_STRATEGY = "retry_strategy"
    CACHING = "caching"
    MEMORY_UTILIZATION = "memory_utilization"


class RiskLevel(StrEnum):
    """Risk severity levels."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    NEGLIGIBLE = "negligible"


class RiskType(StrEnum):
    """Types of risks the system tracks."""

    BUDGET = "budget"
    DEADLINE = "deadline"
    CAPACITY = "capacity"
    RELIABILITY = "reliability"
    SECURITY = "security"
    QUALITY = "quality"
    DEPENDENCY = "dependency"
    OPERATIONAL = "operational"


class IntelligenceReportType(StrEnum):
    """Types of intelligence reports."""

    DAILY_EXECUTIVE = "daily_executive"
    WEEKLY_OPERATIONS = "weekly_operations"
    MONTHLY_PERFORMANCE = "monthly_performance"
    RELIABILITY = "reliability"
    OPTIMIZATION = "optimization"
    RISK = "risk"
    MISSION = "mission"


@dataclass
class ComponentHealth:
    """Health of a single system component."""

    component: str
    score: float = 1.0  # 0.0-1.0
    status: str = "healthy"  # healthy, degraded, unhealthy, unknown
    message: str = ""
    last_checked: datetime = field(default_factory=lambda: datetime.now(UTC))
    metrics: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "component": self.component,
            "score": round(self.score, 4),
            "status": self.status,
            "message": self.message,
            "last_checked": self.last_checked.isoformat(),
            "metrics": dict(self.metrics),
        }


@dataclass
class EnterpriseHealthScore:
    """Composite enterprise health score across all dimensions.

    Each dimension is 0.0-1.0. The overall score is a weighted average.
    """

    operational: float = 1.0
    mission: float = 1.0
    agent_efficiency: float = 1.0
    provider_efficiency: float = 1.0
    workflow_quality: float = 1.0
    execution_success: float = 1.0
    risk_level: float = 1.0  # higher = lower risk
    reliability: float = 1.0
    cost_efficiency: float = 1.0
    learning_velocity: float = 1.0
    innovation: float = 1.0
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    component_health: list[ComponentHealth] = field(default_factory=list)

    # Weights for overall score (must sum to 1.0)
    WEIGHTS: dict[str, float] = field(
        default_factory=lambda: {
            "operational": 0.15,
            "mission": 0.12,
            "agent_efficiency": 0.10,
            "provider_efficiency": 0.08,
            "workflow_quality": 0.10,
            "execution_success": 0.12,
            "risk_level": 0.08,
            "reliability": 0.10,
            "cost_efficiency": 0.07,
            "learning_velocity": 0.04,
            "innovation": 0.04,
        },
    )

    @property
    def overall_score(self) -> float:
        """Weighted average of all dimensions (0.0-1.0)."""
        scores = {
            "operational": self.operational,
            "mission": self.mission,
            "agent_efficiency": self.agent_efficiency,
            "provider_efficiency": self.provider_efficiency,
            "workflow_quality": self.workflow_quality,
            "execution_success": self.execution_success,
            "risk_level": self.risk_level,
            "reliability": self.reliability,
            "cost_efficiency": self.cost_efficiency,
            "learning_velocity": self.learning_velocity,
            "innovation": self.innovation,
        }
        total_weight = sum(self.WEIGHTS.values())
        if total_weight == 0:
            return 0.0
        return sum(scores[dim] * self.WEIGHTS.get(dim, 0) for dim in scores) / total_weight

    @property
    def grade(self) -> str:
        """Letter grade A-F based on overall score."""
        s = self.overall_score
        if s >= 0.95:
            return "A+"
        if s >= 0.90:
            return "A"
        if s >= 0.85:
            return "B+"
        if s >= 0.80:
            return "B"
        if s >= 0.75:
            return "C+"
        if s >= 0.70:
            return "C"
        if s >= 0.60:
            return "D"
        return "F"

    @property
    def status(self) -> str:
        """Overall status: healthy / degraded / critical."""
        s = self.overall_score
        if s >= 0.80:
            return "healthy"
        if s >= 0.60:
            return "degraded"
        return "critical"

    def to_dict(self) -> dict[str, Any]:
        return {
            "operational": round(self.operational, 4),
            "mission": round(self.mission, 4),
            "agent_efficiency": round(self.agent_efficiency, 4),
            "provider_efficiency": round(self.provider_efficiency, 4),
            "workflow_quality": round(self.workflow_quality, 4),
            "execution_success": round(self.execution_success, 4),
            "risk_level": round(self.risk_level, 4),
            "reliability": round(self.reliability, 4),
            "cost_efficiency": round(self.cost_efficiency, 4),
            "learning_velocity": round(self.learning_velocity, 4),
            "innovation": round(self.innovation, 4),
            "overall_score": round(self.overall_score, 4),
            "grade": self.grade,
            "status": self.status,
            "timestamp": self.timestamp.isoformat(),
            "component_health": [c.to_dict() for c in self.component_health],
        }


@dataclass
class OperationalMetrics:
    """Live operational metrics collected from the system."""

    total_missions: int = 0
    active_missions: int = 0
    total_agents: int = 0
    active_agents: int = 0
    total_experiences: int = 0
    total_wbs_nodes: int = 0
    completed_wbs_nodes: int = 0
    total_decisions: int = 0
    total_artifacts: int = 0
    event_bus_throughput_per_s: float = 0.0
    avg_mission_completion_pct: float = 0.0
    avg_agent_reliability: float = 0.0
    avg_provider_reliability: float = 0.0
    total_budget_usd: float = 0.0
    total_spent_usd: float = 0.0
    total_tokens_consumed: int = 0
    memory_usage_mb: float = 0.0
    cpu_usage_pct: float = 0.0
    queue_depth: int = 0
    pending_approvals: int = 0
    open_risks: int = 0
    uptime_s: float = 0.0
    collected_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_missions": self.total_missions,
            "active_missions": self.active_missions,
            "total_agents": self.total_agents,
            "active_agents": self.active_agents,
            "total_experiences": self.total_experiences,
            "total_wbs_nodes": self.total_wbs_nodes,
            "completed_wbs_nodes": self.completed_wbs_nodes,
            "total_decisions": self.total_decisions,
            "total_artifacts": self.total_artifacts,
            "event_bus_throughput_per_s": round(self.event_bus_throughput_per_s, 2),
            "avg_mission_completion_pct": round(self.avg_mission_completion_pct, 2),
            "avg_agent_reliability": round(self.avg_agent_reliability, 4),
            "avg_provider_reliability": round(self.avg_provider_reliability, 4),
            "total_budget_usd": round(self.total_budget_usd, 2),
            "total_spent_usd": round(self.total_spent_usd, 2),
            "total_tokens_consumed": self.total_tokens_consumed,
            "memory_usage_mb": round(self.memory_usage_mb, 2),
            "cpu_usage_pct": round(self.cpu_usage_pct, 2),
            "queue_depth": self.queue_depth,
            "pending_approvals": self.pending_approvals,
            "open_risks": self.open_risks,
            "uptime_s": round(self.uptime_s, 2),
            "collected_at": self.collected_at.isoformat(),
        }


@dataclass
class ForecastResult:
    """A single prediction result."""

    forecast_id: str = field(default_factory=lambda: uuid4().hex[:12])
    forecast_type: str = ForecastType.MISSION_FAILURE.value
    target: str = ""  # what is being predicted (mission_id, agent_id, etc.)
    prediction: str = ""  # human-readable prediction
    probability: float = 0.0  # 0.0-1.0
    confidence: str = ForecastConfidence.MEDIUM.value
    time_horizon: str = "24h"  # 1h, 6h, 24h, 7d, 30d
    evidence: dict[str, Any] = field(default_factory=dict)
    recommended_actions: list[str] = field(default_factory=list)
    forecast_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    valid_until: datetime = field(default_factory=lambda: datetime.now(UTC) + timedelta(hours=24))

    def to_dict(self) -> dict[str, Any]:
        return {
            "forecast_id": self.forecast_id,
            "forecast_type": self.forecast_type,
            "target": self.target,
            "prediction": self.prediction,
            "probability": round(self.probability, 4),
            "confidence": self.confidence,
            "time_horizon": self.time_horizon,
            "evidence": dict(self.evidence),
            "recommended_actions": list(self.recommended_actions),
            "forecast_at": self.forecast_at.isoformat(),
            "valid_until": self.valid_until.isoformat(),
        }


@dataclass
class OptimizationRecommendation:
    """A recommendation for system optimization.

    Recommendations are never applied automatically — they are presented
    to the operator for review and manual application.
    """

    recommendation_id: str = field(default_factory=lambda: uuid4().hex[:12])
    optimization_type: str = OptimizationType.ROUTING.value
    title: str = ""
    description: str = ""
    current_state: str = ""
    recommended_state: str = ""
    expected_improvement: str = ""
    estimated_impact: float = 0.0  # 0.0-1.0
    confidence: float = 0.0  # 0.0-1.0
    priority: str = "normal"  # low, normal, high, critical
    affected_components: list[str] = field(default_factory=list)
    evidence: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    status: str = "pending"  # pending, accepted, rejected, applied

    def to_dict(self) -> dict[str, Any]:
        return {
            "recommendation_id": self.recommendation_id,
            "optimization_type": self.optimization_type,
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
            "created_at": self.created_at.isoformat(),
            "status": self.status,
        }


@dataclass
class RiskAssessment:
    """A risk assessment result."""

    risk_id: str = field(default_factory=lambda: uuid4().hex[:12])
    risk_type: str = RiskType.OPERATIONAL.value
    level: str = RiskLevel.MEDIUM.value
    description: str = ""
    probability: float = 0.5
    impact: float = 0.5
    risk_score: float = 0.25  # probability x impact
    affected_components: list[str] = field(default_factory=list)
    mitigation: str = ""
    evidence: dict[str, Any] = field(default_factory=dict)
    detected_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, Any]:
        return {
            "risk_id": self.risk_id,
            "risk_type": self.risk_type,
            "level": self.level,
            "description": self.description,
            "probability": round(self.probability, 4),
            "impact": round(self.impact, 4),
            "risk_score": round(self.risk_score, 4),
            "affected_components": list(self.affected_components),
            "mitigation": self.mitigation,
            "evidence": dict(self.evidence),
            "detected_at": self.detected_at.isoformat(),
        }


@dataclass
class CapacityForecast:
    """Capacity planning forecast."""

    resource: str = ""  # agents, providers, memory, cpu, budget
    current_usage: float = 0.0
    current_capacity: float = 0.0
    utilization_pct: float = 0.0
    projected_usage_7d: float = 0.0
    projected_usage_30d: float = 0.0
    exhaustion_eta: str | None = None  # ISO date or None
    recommendation: str = ""
    forecast_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, Any]:
        return {
            "resource": self.resource,
            "current_usage": round(self.current_usage, 2),
            "current_capacity": round(self.current_capacity, 2),
            "utilization_pct": round(self.utilization_pct, 2),
            "projected_usage_7d": round(self.projected_usage_7d, 2),
            "projected_usage_30d": round(self.projected_usage_30d, 2),
            "exhaustion_eta": self.exhaustion_eta,
            "recommendation": self.recommendation,
            "forecast_at": self.forecast_at.isoformat(),
        }


@dataclass
class CostBreakdown:
    """Cost analysis breakdown."""

    total_spent_usd: float = 0.0
    total_budget_usd: float = 0.0
    by_provider: dict[str, float] = field(default_factory=dict)
    by_agent: dict[str, float] = field(default_factory=dict)
    by_capability: dict[str, float] = field(default_factory=dict)
    by_mission: dict[str, float] = field(default_factory=dict)
    avg_cost_per_task: float = 0.0
    avg_cost_per_mission: float = 0.0
    cost_trend: list[dict[str, Any]] = field(default_factory=list)
    projected_monthly_spend: float = 0.0
    budget_utilization_pct: float = 0.0
    cost_efficiency_score: float = 0.0  # 0.0-1.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_spent_usd": round(self.total_spent_usd, 2),
            "total_budget_usd": round(self.total_budget_usd, 2),
            "by_provider": {k: round(v, 2) for k, v in self.by_provider.items()},
            "by_agent": {k: round(v, 2) for k, v in self.by_agent.items()},
            "by_capability": {k: round(v, 2) for k, v in self.by_capability.items()},
            "by_mission": {k: round(v, 2) for k, v in self.by_mission.items()},
            "avg_cost_per_task": round(self.avg_cost_per_task, 6),
            "avg_cost_per_mission": round(self.avg_cost_per_mission, 6),
            "cost_trend": list(self.cost_trend),
            "projected_monthly_spend": round(self.projected_monthly_spend, 2),
            "budget_utilization_pct": round(self.budget_utilization_pct, 2),
            "cost_efficiency_score": round(self.cost_efficiency_score, 4),
        }


@dataclass
class CostForecast:
    """Cost prediction result."""

    projected_daily_spend_usd: float = 0.0
    projected_weekly_spend_usd: float = 0.0
    projected_monthly_spend_usd: float = 0.0
    budget_overrun_probability: float = 0.0
    days_until_budget_exhausted: int | None = None
    recommended_budget_adjustment: float = 0.0
    confidence: str = ForecastConfidence.MEDIUM.value

    def to_dict(self) -> dict[str, Any]:
        return {
            "projected_daily_spend_usd": round(self.projected_daily_spend_usd, 2),
            "projected_weekly_spend_usd": round(self.projected_weekly_spend_usd, 2),
            "projected_monthly_spend_usd": round(self.projected_monthly_spend_usd, 2),
            "budget_overrun_probability": round(self.budget_overrun_probability, 4),
            "days_until_budget_exhausted": self.days_until_budget_exhausted,
            "recommended_budget_adjustment": round(self.recommended_budget_adjustment, 2),
            "confidence": self.confidence,
        }


@dataclass
class DigitalTwinNode:
    """A node in the digital twin graph."""

    node_id: str
    node_type: str  # kernel, supervisor, mission_manager, agent, provider, etc.
    name: str = ""
    status: str = "healthy"
    health_score: float = 1.0
    properties: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "node_type": self.node_type,
            "name": self.name,
            "status": self.status,
            "health_score": round(self.health_score, 4),
            "properties": dict(self.properties),
        }


@dataclass
class DigitalTwinSnapshot:
    """A point-in-time snapshot of the entire system as a digital twin."""

    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    nodes: list[DigitalTwinNode] = field(default_factory=list)
    edges: list[dict[str, str]] = field(default_factory=list)
    overall_health: float = 1.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp.isoformat(),
            "nodes": [n.to_dict() for n in self.nodes],
            "edges": list(self.edges),
            "overall_health": round(self.overall_health, 4),
            "node_count": len(self.nodes),
            "edge_count": len(self.edges),
        }


@dataclass
class IntelligenceReport:
    """An intelligence report (daily, weekly, monthly, etc.)."""

    report_id: str = field(default_factory=lambda: uuid4().hex[:12])
    report_type: str = IntelligenceReportType.DAILY_EXECUTIVE.value
    generated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    period_start: datetime = field(default_factory=lambda: datetime.now(UTC))
    period_end: datetime = field(default_factory=lambda: datetime.now(UTC))
    health_score: EnterpriseHealthScore = field(default_factory=EnterpriseHealthScore)
    operational_metrics: OperationalMetrics = field(default_factory=OperationalMetrics)
    forecasts: list[ForecastResult] = field(default_factory=list)
    recommendations: list[OptimizationRecommendation] = field(default_factory=list)
    risks: list[RiskAssessment] = field(default_factory=list)
    capacity: list[CapacityForecast] = field(default_factory=list)
    cost: CostBreakdown = field(default_factory=CostBreakdown)
    summary: str = ""
    key_findings: list[str] = field(default_factory=list)
    action_items: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "report_id": self.report_id,
            "report_type": self.report_type,
            "generated_at": self.generated_at.isoformat(),
            "period_start": self.period_start.isoformat(),
            "period_end": self.period_end.isoformat(),
            "health_score": self.health_score.to_dict(),
            "operational_metrics": self.operational_metrics.to_dict(),
            "forecasts": [f.to_dict() for f in self.forecasts],
            "recommendations": [r.to_dict() for r in self.recommendations],
            "risks": [r.to_dict() for r in self.risks],
            "capacity": [c.to_dict() for c in self.capacity],
            "cost": self.cost.to_dict(),
            "summary": self.summary,
            "key_findings": list(self.key_findings),
            "action_items": list(self.action_items),
        }
