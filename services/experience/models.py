"""Experience models — immutable records of every execution.

An ExperienceRecord captures the full lifecycle of a task: what was asked,
which agent/provider served it, how long it took, whether it succeeded,
what QA/reflection said about it, and what it cost.

Records are immutable (frozen dataclass) and JSON-serializable. The store
persists them to disk; the indexer builds in-memory indices for fast
retrieval; the analyzer mines them for patterns.
"""

from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

__all__ = [
    "ArtifactRef",
    "ExecutionStep",
    "ExperienceOutcome",
    "ExperienceRecord",
    "KnowledgeRef",
    "ResourceUsage",
    "TokenUsage",
    "UserFeedback",
]


class ExperienceOutcome(StrEnum):
    """Outcome of an experience."""

    SUCCESS = "success"
    FAILURE = "failure"
    PARTIAL = "partial"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"


@dataclass(frozen=True)
class TokenUsage:
    """Token usage for an LLM call."""

    input_tokens: int = 0
    output_tokens: int = 0
    reasoning_tokens: int = 0
    cached_tokens: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens + self.reasoning_tokens


@dataclass(frozen=True)
class ResourceUsage:
    """Resource usage for an execution."""

    cpu_seconds: float = 0.0
    memory_peak_mb: float = 0.0
    disk_mb: float = 0.0
    network_bytes_in: int = 0
    network_bytes_out: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class KnowledgeRef:
    """A reference to a memory item used during execution."""

    memory_id: UUID
    scope: str
    relevance_score: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "memory_id": str(self.memory_id),
            "scope": self.scope,
            "relevance_score": self.relevance_score,
        }


@dataclass(frozen=True)
class ArtifactRef:
    """A reference to an artifact produced during execution."""

    artifact_id: str
    artifact_type: str  # "file", "code", "document", "image", etc.
    path: str | None = None
    size_bytes: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "artifact_id": self.artifact_id,
            "artifact_type": self.artifact_type,
            "path": self.path,
            "size_bytes": self.size_bytes,
        }


@dataclass(frozen=True)
class UserFeedback:
    """User feedback on an execution."""

    rating: int = 0  # 1-5 (0 = no feedback)
    comment: str = ""
    approved: bool | None = None  # True=approved, False=rejected, None=no review

    def to_dict(self) -> dict[str, Any]:
        return {
            "rating": self.rating,
            "comment": self.comment,
            "approved": self.approved,
        }


@dataclass(frozen=True)
class ExecutionStep:
    """A single step in the execution plan."""

    step_id: str
    goal: str
    capability: str
    agent_id: str | None = None
    status: str = "pending"  # pending, running, succeeded, failed, skipped
    duration_s: float = 0.0
    retries: int = 0
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ExperienceRecord:
    """An immutable record of a single task execution.

    Captures the full lifecycle: what was asked, who served it, how it went,
    what it cost, and what was learned. Records are persisted to disk and
    indexed for fast retrieval.
    """

    # Task context (required — must come before defaulted fields)
    task_id: UUID
    agent_id: str
    agent_type: str

    # Identity (have defaults)
    experience_id: UUID = field(default_factory=uuid4)
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    workflow_id: str | None = None
    correlation_id: UUID | None = None

    # Agent + provider
    provider: str | None = None
    model: str | None = None
    capabilities_used: list[str] = field(default_factory=list)

    # Goal + plan
    goal: str = ""
    plan: list[ExecutionStep] = field(default_factory=list)
    input_summary: str = ""

    # Execution
    output_summary: str = ""
    execution_time_s: float = 0.0
    latency_s: float = 0.0
    retries: int = 0

    # Quality scores
    reflection_score: float = 0.0  # 0.0-1.0
    qa_score: float = 0.0  # 0.0-1.0
    user_feedback: UserFeedback = field(default_factory=UserFeedback)

    # Outcome
    outcome: str = ExperienceOutcome.SUCCESS.value
    success: bool = True
    failure_reason: str | None = None
    recovery_action: str | None = None

    # Resources + cost
    resource_usage: ResourceUsage = field(default_factory=ResourceUsage)
    cost_usd: float = 0.0
    token_usage: TokenUsage = field(default_factory=TokenUsage)

    # Confidence + context
    confidence: float = 0.0  # 0.0-1.0
    context_hash: str = ""

    # Knowledge + artifacts
    knowledge_references: list[KnowledgeRef] = field(default_factory=list)
    artifacts_produced: list[ArtifactRef] = field(default_factory=list)

    def __post_init__(self) -> None:
        """Compute context hash if not set."""
        if not self.context_hash:
            content = f"{self.agent_id}:{self.goal}:{self.input_summary}"
            object.__setattr__(
                self,
                "context_hash",
                hashlib.sha256(content.encode("utf-8")).hexdigest()[:16],
            )

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-compatible dict."""
        return {
            "experience_id": str(self.experience_id),
            "timestamp": self.timestamp.isoformat(),
            "task_id": str(self.task_id),
            "workflow_id": self.workflow_id,
            "correlation_id": str(self.correlation_id) if self.correlation_id else None,
            "agent_id": self.agent_id,
            "agent_type": self.agent_type,
            "provider": self.provider,
            "model": self.model,
            "capabilities_used": list(self.capabilities_used),
            "goal": self.goal,
            "plan": [s.to_dict() for s in self.plan],
            "input_summary": self.input_summary,
            "output_summary": self.output_summary,
            "execution_time_s": self.execution_time_s,
            "latency_s": self.latency_s,
            "retries": self.retries,
            "reflection_score": self.reflection_score,
            "qa_score": self.qa_score,
            "user_feedback": self.user_feedback.to_dict(),
            "outcome": self.outcome,
            "success": self.success,
            "failure_reason": self.failure_reason,
            "recovery_action": self.recovery_action,
            "resource_usage": self.resource_usage.to_dict(),
            "cost_usd": self.cost_usd,
            "token_usage": self.token_usage.to_dict(),
            "confidence": self.confidence,
            "context_hash": self.context_hash,
            "knowledge_references": [k.to_dict() for k in self.knowledge_references],
            "artifacts_produced": [a.to_dict() for a in self.artifacts_produced],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ExperienceRecord:
        """Deserialize from a dict."""
        # Parse nested fields
        plan = [ExecutionStep(**s) for s in data.get("plan", [])]
        resource_usage = ResourceUsage(**data.get("resource_usage", {}))
        token_usage = TokenUsage(**data.get("token_usage", {}))
        user_feedback = UserFeedback(**data.get("user_feedback", {}))
        knowledge_refs = [KnowledgeRef(**k) for k in data.get("knowledge_references", [])]
        artifacts = [ArtifactRef(**a) for a in data.get("artifacts_produced", [])]
        return cls(
            experience_id=UUID(data["experience_id"]),
            timestamp=datetime.fromisoformat(data["timestamp"]),
            task_id=UUID(data["task_id"]),
            workflow_id=data.get("workflow_id"),
            correlation_id=UUID(data["correlation_id"]) if data.get("correlation_id") else None,
            agent_id=data["agent_id"],
            agent_type=data["agent_type"],
            provider=data.get("provider"),
            model=data.get("model"),
            capabilities_used=list(data.get("capabilities_used", [])),
            goal=data.get("goal", ""),
            plan=plan,
            input_summary=data.get("input_summary", ""),
            output_summary=data.get("output_summary", ""),
            execution_time_s=data.get("execution_time_s", 0.0),
            latency_s=data.get("latency_s", 0.0),
            retries=data.get("retries", 0),
            reflection_score=data.get("reflection_score", 0.0),
            qa_score=data.get("qa_score", 0.0),
            user_feedback=user_feedback,
            outcome=data.get("outcome", ExperienceOutcome.SUCCESS.value),
            success=data.get("success", True),
            failure_reason=data.get("failure_reason"),
            recovery_action=data.get("recovery_action"),
            resource_usage=resource_usage,
            cost_usd=data.get("cost_usd", 0.0),
            token_usage=token_usage,
            confidence=data.get("confidence", 0.0),
            context_hash=data.get("context_hash", ""),
            knowledge_references=knowledge_refs,
            artifacts_produced=artifacts,
        )

    def quality_score(self) -> float:
        """Composite quality score (0.0-1.0) combining reflection + QA + user feedback.

        Weights: reflection 30%, QA 40%, user feedback 30% (if present).
        """
        score = self.reflection_score * 0.3 + self.qa_score * 0.4
        if self.user_feedback.rating > 0:
            score += (self.user_feedback.rating / 5.0) * 0.3
        else:
            # No user feedback — reweight to reflection + QA only
            score = self.reflection_score * 0.4286 + self.qa_score * 0.5714
        return min(1.0, max(0.0, score))
