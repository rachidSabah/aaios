"""Mission models — the organizational unit above tasks and workflows.

A Mission is a large, long-running objective that gets decomposed into a
Work Breakdown Structure (WBS): programs → projects → epics → stories →
tasks → subtasks. Each WBS node has a type, status, dependencies, and
assigned agents/providers.

Missions have a state machine (created → planning → executing → paused →
completed/failed/cancelled), a budget, time constraints, a risk register,
milestones, approval gates, and lessons learned.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4

__all__ = [
    "ApprovalGate",
    "ApprovalStatus",
    "Budget",
    "Decision",
    "DecisionType",
    "ExecutiveRole",
    "Mission",
    "MissionArtifact",
    "MissionMetrics",
    "MissionPriority",
    "MissionStatus",
    "Milestone",
    "QualityMetrics",
    "ResourceAllocation",
    "Risk",
    "RiskSeverity",
    "WBSNode",
    "WBSType",
]


class MissionStatus(StrEnum):
    """Mission lifecycle states."""

    CREATED = "created"
    PLANNING = "planning"
    READY = "ready"
    EXECUTING = "executing"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class MissionPriority(StrEnum):
    """Mission priority levels."""

    CRITICAL = "critical"
    HIGH = "high"
    NORMAL = "normal"
    LOW = "low"
    BACKGROUND = "background"


class WBSType(StrEnum):
    """Work Breakdown Structure node types."""

    PROGRAM = "program"
    PROJECT = "project"
    EPIC = "epic"
    FEATURE = "feature"
    STORY = "story"
    TASK = "task"
    SUBTASK = "subtask"


class ExecutiveRole(StrEnum):
    """Executive roles in the organizational hierarchy."""

    EXECUTIVE_DIRECTOR = "executive_director"
    CHIEF_STRATEGY_OFFICER = "chief_strategy_officer"
    MISSION_DIRECTOR = "mission_director"
    MISSION_PLANNER = "mission_planner"
    MISSION_SUPERVISOR = "mission_supervisor"
    TASK_SUPERVISOR = "task_supervisor"


class DecisionType(StrEnum):
    """Types of executive decisions."""

    START = "start"
    PAUSE = "pause"
    RESUME = "resume"
    CANCEL = "cancel"
    REPLAN = "replan"
    MERGE_TASKS = "merge_tasks"
    SPLIT_TASK = "split_task"
    SWITCH_PROVIDER = "switch_provider"
    SWITCH_AGENT = "switch_agent"
    REQUEST_APPROVAL = "request_approval"
    CONSULT_MEMORY = "consult_memory"
    REFLECT = "reflect"
    CONTINUE = "continue"
    RESEARCH = "research"


class RiskSeverity(StrEnum):
    """Risk severity levels."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    NEGLIGIBLE = "negligible"


class ApprovalStatus(StrEnum):
    """Approval gate status."""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    WAIVED = "waived"


@dataclass
class Budget:
    """Mission budget tracking."""

    total_usd: float = 0.0
    spent_usd: float = 0.0
    reserved_usd: float = 0.0
    max_cost_per_task_usd: float = 1.0
    alert_threshold_pct: float = 80.0  # alert at 80% spent

    @property
    def remaining_usd(self) -> float:
        return self.total_usd - self.spent_usd - self.reserved_usd

    @property
    def utilization_pct(self) -> float:
        if self.total_usd <= 0:
            return 0.0
        return (self.spent_usd / self.total_usd) * 100.0

    @property
    def is_over_budget(self) -> bool:
        return self.spent_usd > self.total_usd

    @property
    def is_alert(self) -> bool:
        return self.utilization_pct >= self.alert_threshold_pct

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_usd": round(self.total_usd, 6),
            "spent_usd": round(self.spent_usd, 6),
            "reserved_usd": round(self.reserved_usd, 6),
            "remaining_usd": round(self.remaining_usd, 6),
            "max_cost_per_task_usd": round(self.max_cost_per_task_usd, 6),
            "utilization_pct": round(self.utilization_pct, 2),
            "is_over_budget": self.is_over_budget,
            "is_alert": self.is_alert,
        }


@dataclass
class QualityMetrics:
    """Quality metrics for a mission or WBS node."""

    reflection_score: float = 0.0  # 0.0-1.0
    qa_score: float = 0.0  # 0.0-1.0
    user_satisfaction: float = 0.0  # 0.0-1.0
    defect_count: int = 0
    rework_count: int = 0
    test_pass_rate: float = 0.0

    @property
    def composite_score(self) -> float:
        """Weighted composite quality score (0.0-1.0)."""
        score = self.reflection_score * 0.3 + self.qa_score * 0.4 + self.user_satisfaction * 0.3
        return min(1.0, max(0.0, score))

    def to_dict(self) -> dict[str, Any]:
        return {
            "reflection_score": round(self.reflection_score, 4),
            "qa_score": round(self.qa_score, 4),
            "user_satisfaction": round(self.user_satisfaction, 4),
            "defect_count": self.defect_count,
            "rework_count": self.rework_count,
            "test_pass_rate": round(self.test_pass_rate, 4),
            "composite_score": round(self.composite_score, 4),
        }


@dataclass
class Risk:
    """A risk in the mission risk register."""

    risk_id: str = field(default_factory=lambda: uuid4().hex[:12])
    description: str = ""
    severity: str = RiskSeverity.MEDIUM.value
    probability: float = 0.5  # 0.0-1.0
    impact: float = 0.5  # 0.0-1.0
    mitigation: str = ""
    owner: str | None = None
    identified_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    resolved_at: datetime | None = None
    status: str = "open"  # open, mitigated, resolved, materialized

    @property
    def risk_score(self) -> float:
        """Risk score = probability x impact (0.0-1.0)."""
        return self.probability * self.impact

    def to_dict(self) -> dict[str, Any]:
        return {
            "risk_id": self.risk_id,
            "description": self.description,
            "severity": self.severity,
            "probability": round(self.probability, 4),
            "impact": round(self.impact, 4),
            "risk_score": round(self.risk_score, 4),
            "mitigation": self.mitigation,
            "owner": self.owner,
            "identified_at": self.identified_at.isoformat(),
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
            "status": self.status,
        }


@dataclass
class Milestone:
    """A mission milestone."""

    milestone_id: str = field(default_factory=lambda: uuid4().hex[:12])
    title: str = ""
    description: str = ""
    target_date: datetime | None = None
    achieved_date: datetime | None = None
    status: str = "pending"  # pending, in_progress, achieved, missed
    wbs_node_ids: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "milestone_id": self.milestone_id,
            "title": self.title,
            "description": self.description,
            "target_date": self.target_date.isoformat() if self.target_date else None,
            "achieved_date": self.achieved_date.isoformat() if self.achieved_date else None,
            "status": self.status,
            "wbs_node_ids": list(self.wbs_node_ids),
        }


@dataclass
class ApprovalGate:
    """An approval gate in the mission."""

    gate_id: str = field(default_factory=lambda: uuid4().hex[:12])
    title: str = ""
    description: str = ""
    wbs_node_id: str | None = None
    status: str = ApprovalStatus.PENDING.value
    requested_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    decided_at: datetime | None = None
    decided_by: str | None = None
    decision_reason: str | None = None
    approver_role: str = ExecutiveRole.MISSION_DIRECTOR.value

    def to_dict(self) -> dict[str, Any]:
        return {
            "gate_id": self.gate_id,
            "title": self.title,
            "description": self.description,
            "wbs_node_id": self.wbs_node_id,
            "status": self.status,
            "requested_at": self.requested_at.isoformat(),
            "decided_at": self.decided_at.isoformat() if self.decided_at else None,
            "decided_by": self.decided_by,
            "decision_reason": self.decision_reason,
            "approver_role": self.approver_role,
        }


@dataclass
class MissionArtifact:
    """An artifact produced by a mission."""

    artifact_id: str = field(default_factory=lambda: uuid4().hex[:12])
    name: str = ""
    artifact_type: str = "file"  # file, code, document, image, dataset, etc.
    path: str | None = None
    size_bytes: int = 0
    checksum: str | None = None
    produced_by_wbs: str | None = None
    produced_by_agent: str | None = None
    produced_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "artifact_id": self.artifact_id,
            "name": self.name,
            "artifact_type": self.artifact_type,
            "path": self.path,
            "size_bytes": self.size_bytes,
            "checksum": self.checksum,
            "produced_by_wbs": self.produced_by_wbs,
            "produced_by_agent": self.produced_by_agent,
            "produced_at": self.produced_at.isoformat(),
            "metadata": dict(self.metadata),
        }


@dataclass
class ResourceAllocation:
    """Resource allocation for a mission."""

    assigned_agents: list[str] = field(default_factory=list)
    assigned_providers: list[str] = field(default_factory=list)
    max_concurrent_tasks: int = 10
    max_concurrent_agents: int = 50
    memory_limit_mb: int = 4096
    cpu_cores: float = 4.0
    gpu_count: int = 0
    storage_limit_mb: int = 10240
    network_bandwidth_mbps: int = 100

    def to_dict(self) -> dict[str, Any]:
        return {
            "assigned_agents": list(self.assigned_agents),
            "assigned_providers": list(self.assigned_providers),
            "max_concurrent_tasks": self.max_concurrent_tasks,
            "max_concurrent_agents": self.max_concurrent_agents,
            "memory_limit_mb": self.memory_limit_mb,
            "cpu_cores": self.cpu_cores,
            "gpu_count": self.gpu_count,
            "storage_limit_mb": self.storage_limit_mb,
            "network_bandwidth_mbps": self.network_bandwidth_mbps,
        }


@dataclass
class WBSNode:
    """A node in the Work Breakdown Structure.

    WBS nodes form a tree: program → project → epic → feature → story →
    task → subtask. Each node can have dependencies on other nodes and
    an assigned agent + provider.
    """

    node_id: str = field(default_factory=lambda: uuid4().hex[:12])
    parent_id: str | None = None
    node_type: str = WBSType.TASK.value
    title: str = ""
    description: str = ""
    status: str = "pending"  # pending, ready, running, succeeded, failed, skipped, blocked
    priority: str = MissionPriority.NORMAL.value
    depends_on: list[str] = field(default_factory=list)  # other node_ids
    assigned_agent_id: str | None = None
    assigned_provider: str | None = None
    assigned_model: str | None = None
    capabilities_required: list[str] = field(default_factory=list)
    estimated_duration_s: float = 0.0
    actual_duration_s: float = 0.0
    estimated_cost_usd: float = 0.0
    actual_cost_usd: float = 0.0
    approval_gate_id: str | None = None
    artifacts_produced: list[str] = field(default_factory=list)  # artifact_ids
    lessons_learned: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    started_at: datetime | None = None
    completed_at: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "parent_id": self.parent_id,
            "node_type": self.node_type,
            "title": self.title,
            "description": self.description,
            "status": self.status,
            "priority": self.priority,
            "depends_on": list(self.depends_on),
            "assigned_agent_id": self.assigned_agent_id,
            "assigned_provider": self.assigned_provider,
            "assigned_model": self.assigned_model,
            "capabilities_required": list(self.capabilities_required),
            "estimated_duration_s": self.estimated_duration_s,
            "actual_duration_s": self.actual_duration_s,
            "estimated_cost_usd": round(self.estimated_cost_usd, 6),
            "actual_cost_usd": round(self.actual_cost_usd, 6),
            "approval_gate_id": self.approval_gate_id,
            "artifacts_produced": list(self.artifacts_produced),
            "lessons_learned": self.lessons_learned,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "metadata": dict(self.metadata),
        }


@dataclass
class Decision:
    """An executive decision made during mission execution."""

    decision_id: str = field(default_factory=lambda: uuid4().hex[:12])
    mission_id: str = ""
    decision_type: str = DecisionType.CONTINUE.value
    made_by: str = ExecutiveRole.MISSION_SUPERVISOR.value
    made_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    reasoning: str = ""
    evidence: dict[str, Any] = field(default_factory=dict)
    action_taken: str | None = None
    affected_wbs_node_ids: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision_id": self.decision_id,
            "mission_id": self.mission_id,
            "decision_type": self.decision_type,
            "made_by": self.made_by,
            "made_at": self.made_at.isoformat(),
            "reasoning": self.reasoning,
            "evidence": dict(self.evidence),
            "action_taken": self.action_taken,
            "affected_wbs_node_ids": list(self.affected_wbs_node_ids),
        }


@dataclass
class MissionMetrics:
    """Aggregated metrics for a mission."""

    total_wbs_nodes: int = 0
    completed_nodes: int = 0
    failed_nodes: int = 0
    in_progress_nodes: int = 0
    blocked_nodes: int = 0
    total_tasks: int = 0
    completed_tasks: int = 0
    total_artifacts: int = 0
    total_decisions: int = 0
    total_approvals: int = 0
    pending_approvals: int = 0
    total_agent_assignments: int = 0
    total_provider_switches: int = 0
    total_replans: int = 0
    total_retries: int = 0

    @property
    def completion_pct(self) -> float:
        if self.total_wbs_nodes == 0:
            return 0.0
        return (self.completed_nodes / self.total_wbs_nodes) * 100.0

    @property
    def task_completion_pct(self) -> float:
        if self.total_tasks == 0:
            return 0.0
        return (self.completed_tasks / self.total_tasks) * 100.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_wbs_nodes": self.total_wbs_nodes,
            "completed_nodes": self.completed_nodes,
            "failed_nodes": self.failed_nodes,
            "in_progress_nodes": self.in_progress_nodes,
            "blocked_nodes": self.blocked_nodes,
            "total_tasks": self.total_tasks,
            "completed_tasks": self.completed_tasks,
            "total_artifacts": self.total_artifacts,
            "total_decisions": self.total_decisions,
            "total_approvals": self.total_approvals,
            "pending_approvals": self.pending_approvals,
            "total_agent_assignments": self.total_agent_assignments,
            "total_provider_switches": self.total_provider_switches,
            "total_replans": self.total_replans,
            "total_retries": self.total_retries,
            "completion_pct": round(self.completion_pct, 2),
            "task_completion_pct": round(self.task_completion_pct, 2),
        }


@dataclass
class Mission:
    """A Mission — the top-level organizational unit.

    A Mission represents a large, long-running objective that gets
    decomposed into a Work Breakdown Structure. It has a budget, time
    constraints, a risk register, milestones, approval gates, and
    lessons learned.
    """

    mission_id: str = field(default_factory=lambda: uuid4().hex[:16])
    title: str = ""
    description: str = ""
    objectives: list[str] = field(default_factory=list)
    deliverables: list[str] = field(default_factory=list)
    priority: str = MissionPriority.NORMAL.value
    status: str = MissionStatus.CREATED.value

    # Budget + time
    budget: Budget = field(default_factory=Budget)
    deadline: datetime | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    # WBS
    wbs_nodes: list[WBSNode] = field(default_factory=list)

    # Risk + milestones + approvals
    risks: list[Risk] = field(default_factory=list)
    milestones: list[Milestone] = field(default_factory=list)
    approval_gates: list[ApprovalGate] = field(default_factory=list)

    # Resources
    resources: ResourceAllocation = field(default_factory=ResourceAllocation)

    # Quality + progress
    quality: QualityMetrics = field(default_factory=QualityMetrics)
    metrics: MissionMetrics = field(default_factory=MissionMetrics)

    # Decisions + artifacts + lessons
    decisions: list[Decision] = field(default_factory=list)
    artifacts: list[MissionArtifact] = field(default_factory=list)
    lessons_learned: list[str] = field(default_factory=list)

    # Dependencies on other missions
    depends_on_missions: list[str] = field(default_factory=list)

    # Metadata
    owner: str | None = None
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    # Executive assignment
    mission_director: str | None = None
    mission_supervisor: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "mission_id": self.mission_id,
            "title": self.title,
            "description": self.description,
            "objectives": list(self.objectives),
            "deliverables": list(self.deliverables),
            "priority": self.priority,
            "status": self.status,
            "budget": self.budget.to_dict(),
            "deadline": self.deadline.isoformat() if self.deadline else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "wbs_nodes": [n.to_dict() for n in self.wbs_nodes],
            "risks": [r.to_dict() for r in self.risks],
            "milestones": [m.to_dict() for m in self.milestones],
            "approval_gates": [g.to_dict() for g in self.approval_gates],
            "resources": self.resources.to_dict(),
            "quality": self.quality.to_dict(),
            "metrics": self.metrics.to_dict(),
            "decisions": [d.to_dict() for d in self.decisions],
            "artifacts": [a.to_dict() for a in self.artifacts],
            "lessons_learned": list(self.lessons_learned),
            "depends_on_missions": list(self.depends_on_missions),
            "owner": self.owner,
            "tags": list(self.tags),
            "metadata": dict(self.metadata),
            "mission_director": self.mission_director,
            "mission_supervisor": self.mission_supervisor,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Mission:
        """Deserialize from a dict."""
        # Filter budget to only constructor fields (exclude computed properties)
        budget_data = data.get("budget", {})
        budget_fields = {
            "total_usd",
            "spent_usd",
            "reserved_usd",
            "max_cost_per_task_usd",
            "alert_threshold_pct",
        }
        budget = (
            Budget(**{k: v for k, v in budget_data.items() if k in budget_fields})
            if budget_data
            else Budget()
        )

        # Filter quality to only constructor fields
        quality_data = data.get("quality", {})
        quality_fields = {
            "reflection_score",
            "qa_score",
            "user_satisfaction",
            "defect_count",
            "rework_count",
            "test_pass_rate",
        }
        quality = (
            QualityMetrics(**{k: v for k, v in quality_data.items() if k in quality_fields})
            if quality_data
            else QualityMetrics()
        )

        # Filter resources to only constructor fields
        resources_data = data.get("resources", {})
        resource_fields = {
            "assigned_agents",
            "assigned_providers",
            "max_concurrent_tasks",
            "max_concurrent_agents",
            "memory_limit_mb",
            "cpu_cores",
            "gpu_count",
            "storage_limit_mb",
            "network_bandwidth_mbps",
        }
        resources = (
            ResourceAllocation(**{k: v for k, v in resources_data.items() if k in resource_fields})
            if resources_data
            else ResourceAllocation()
        )

        wbs_nodes = [WBSNode(**n) for n in data.get("wbs_nodes", [])]
        risks = [Risk(**r) for r in data.get("risks", [])]
        milestones = [Milestone(**m) for m in data.get("milestones", [])]
        gates = [ApprovalGate(**g) for g in data.get("approval_gates", [])]
        decisions = [Decision(**d) for d in data.get("decisions", [])]
        artifacts = [MissionArtifact(**a) for a in data.get("artifacts", [])]

        def _parse_dt(s: str | None) -> datetime | None:
            if not s:
                return None
            try:
                return datetime.fromisoformat(s)
            except (ValueError, TypeError):
                return None

        return cls(
            mission_id=data.get("mission_id", uuid4().hex[:16]),
            title=data.get("title", ""),
            description=data.get("description", ""),
            objectives=list(data.get("objectives", [])),
            deliverables=list(data.get("deliverables", [])),
            priority=data.get("priority", MissionPriority.NORMAL.value),
            status=data.get("status", MissionStatus.CREATED.value),
            budget=budget,
            deadline=_parse_dt(data.get("deadline")),
            started_at=_parse_dt(data.get("started_at")),
            completed_at=_parse_dt(data.get("completed_at")),
            created_at=_parse_dt(data.get("created_at")) or datetime.now(UTC),
            updated_at=_parse_dt(data.get("updated_at")) or datetime.now(UTC),
            wbs_nodes=wbs_nodes,
            risks=risks,
            milestones=milestones,
            approval_gates=gates,
            resources=resources,
            quality=quality,
            decisions=decisions,
            artifacts=artifacts,
            lessons_learned=list(data.get("lessons_learned", [])),
            depends_on_missions=list(data.get("depends_on_missions", [])),
            owner=data.get("owner"),
            tags=list(data.get("tags", [])),
            metadata=dict(data.get("metadata", {})),
            mission_director=data.get("mission_director"),
            mission_supervisor=data.get("mission_supervisor"),
        )

    def get_wbs_node(self, node_id: str) -> WBSNode | None:
        """Find a WBS node by ID."""
        for node in self.wbs_nodes:
            if node.node_id == node_id:
                return node
        return None

    def get_children(self, parent_id: str) -> list[WBSNode]:
        """Get all direct children of a WBS node."""
        return [n for n in self.wbs_nodes if n.parent_id == parent_id]

    def get_root_nodes(self) -> list[WBSNode]:
        """Get all root WBS nodes (no parent)."""
        return [n for n in self.wbs_nodes if n.parent_id is None]

    def get_ready_nodes(self) -> list[WBSNode]:
        """Get all WBS nodes that are ready to execute (dependencies met, status=pending)."""
        completed_ids = {n.node_id for n in self.wbs_nodes if n.status == "succeeded"}
        ready: list[WBSNode] = []
        for node in self.wbs_nodes:
            if node.status != "pending":
                continue
            if all(dep in completed_ids for dep in node.depends_on):
                ready.append(node)
        return ready

    def is_terminal(self) -> bool:
        """Check if the mission is in a terminal state."""
        return self.status in (
            MissionStatus.COMPLETED.value,
            MissionStatus.FAILED.value,
            MissionStatus.CANCELLED.value,
        )

    def elapsed_s(self) -> float:
        """Elapsed time since mission started (or 0)."""
        if not self.started_at:
            return 0.0
        end = self.completed_at or datetime.now(UTC)
        return (end - self.started_at).total_seconds()

    def time_remaining_s(self) -> float | None:
        """Seconds until deadline, or None if no deadline."""
        if not self.deadline:
            return None
        return (self.deadline - datetime.now(UTC)).total_seconds()
