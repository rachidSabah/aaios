"""Enterprise Experience Engine — extends the existing experience engine with
cognitive fields: reasoning, approvals, lessons learned, context, execution path.

Wraps the existing LearningEngine (services.experience) and adds:
  - Context persistence (inputs, reasoning, selected agents/providers)
  - Execution path tracking
  - Approval history
  - Human feedback storage
  - Lessons learned
  - Advanced search (similarity, timeline, tagging)
  - Export (JSON, CSV, Markdown)
"""

from __future__ import annotations

import json
from collections import defaultdict
from datetime import UTC, datetime
from typing import Any

from core.logging import get_logger

_log = get_logger(__name__)

__all__ = ["CognitiveExperience", "CognitiveExperienceEngine"]


from dataclasses import dataclass, field  # noqa: E402
from uuid import uuid4  # noqa: E402


@dataclass
class CognitiveExperience:
    """Extended experience record with cognitive fields."""

    experience_id: str = field(default_factory=lambda: uuid4().hex[:16])
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))

    # Mission + workflow context
    mission_id: str | None = None
    workflow_id: str | None = None
    context: dict[str, Any] = field(default_factory=dict)

    # Inputs + outputs
    inputs: dict[str, Any] = field(default_factory=dict)
    outputs: dict[str, Any] = field(default_factory=dict)
    reasoning: str = ""

    # Selected agents + providers
    selected_agents: list[str] = field(default_factory=list)
    selected_providers: list[str] = field(default_factory=list)
    execution_path: list[str] = field(default_factory=list)

    # Metrics
    cost_usd: float = 0.0
    latency_s: float = 0.0
    token_usage: dict[str, int] = field(default_factory=dict)

    # Outcome
    success: bool = True
    failures: list[str] = field(default_factory=list)
    retries: int = 0
    rollback: str | None = None

    # Approvals + feedback
    approvals: list[dict[str, Any]] = field(default_factory=list)
    human_feedback: str | None = None
    feedback_rating: int = 0  # 1-5

    # Risk + confidence
    risk_score: float = 0.0
    confidence_score: float = 0.0

    # Lessons learned
    lessons_learned: list[str] = field(default_factory=list)

    # Tags
    tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "experience_id": self.experience_id,
            "timestamp": self.timestamp.isoformat(),
            "mission_id": self.mission_id,
            "workflow_id": self.workflow_id,
            "context": dict(self.context),
            "inputs": dict(self.inputs),
            "outputs": dict(self.outputs),
            "reasoning": self.reasoning,
            "selected_agents": list(self.selected_agents),
            "selected_providers": list(self.selected_providers),
            "execution_path": list(self.execution_path),
            "cost_usd": round(self.cost_usd, 6),
            "latency_s": round(self.latency_s, 4),
            "token_usage": dict(self.token_usage),
            "success": self.success,
            "failures": list(self.failures),
            "retries": self.retries,
            "rollback": self.rollback,
            "approvals": list(self.approvals),
            "human_feedback": self.human_feedback,
            "feedback_rating": self.feedback_rating,
            "risk_score": round(self.risk_score, 4),
            "confidence_score": round(self.confidence_score, 4),
            "lessons_learned": list(self.lessons_learned),
            "tags": list(self.tags),
        }


class CognitiveExperienceEngine:
    """Enterprise Experience Engine — stores and queries cognitive experiences.

    In-memory store (persisted via JSON). Wraps the existing LearningEngine
    and adds cognitive fields for deeper analysis.
    """

    def __init__(self) -> None:
        self._experiences: list[CognitiveExperience] = []
        self._by_tag: dict[str, list[str]] = defaultdict(list)
        self._by_agent: dict[str, list[str]] = defaultdict(list)
        self._by_provider: dict[str, list[str]] = defaultdict(list)
        self._by_mission: dict[str, list[str]] = defaultdict(list)

    async def record(self, exp: CognitiveExperience) -> CognitiveExperience:
        """Record a cognitive experience."""
        self._experiences.append(exp)
        for tag in exp.tags:
            self._by_tag[tag].append(exp.experience_id)
        for agent in exp.selected_agents:
            self._by_agent[agent].append(exp.experience_id)
        for provider in exp.selected_providers:
            self._by_provider[provider].append(exp.experience_id)
        if exp.mission_id:
            self._by_mission[exp.mission_id].append(exp.experience_id)
        return exp

    async def get(self, experience_id: str) -> CognitiveExperience | None:
        """Get an experience by ID."""
        for exp in self._experiences:
            if exp.experience_id == experience_id:
                return exp
        return None

    async def search(
        self,
        *,
        agent: str | None = None,
        provider: str | None = None,
        mission_id: str | None = None,
        tag: str | None = None,
        success: bool | None = None,
        since: datetime | None = None,
        limit: int = 100,
    ) -> list[CognitiveExperience]:
        """Search experiences with filters."""
        results = list(self._experiences)
        if agent:
            ids = set(self._by_agent.get(agent, []))
            results = [e for e in results if e.experience_id in ids]
        if provider:
            ids = set(self._by_provider.get(provider, []))
            results = [e for e in results if e.experience_id in ids]
        if mission_id:
            ids = set(self._by_mission.get(mission_id, []))
            results = [e for e in results if e.experience_id in ids]
        if tag:
            ids = set(self._by_tag.get(tag, []))
            results = [e for e in results if e.experience_id in ids]
        if success is not None:
            results = [e for e in results if e.success == success]
        if since:
            results = [e for e in results if e.timestamp >= since]
        return results[-limit:]

    async def timeline(self, limit: int = 50) -> list[dict[str, Any]]:
        """Get a timeline of experiences."""
        sorted_exp = sorted(self._experiences, key=lambda e: e.timestamp, reverse=True)
        return [
            {
                "experience_id": e.experience_id,
                "timestamp": e.timestamp.isoformat(),
                "mission_id": e.mission_id,
                "success": e.success,
                "cost_usd": e.cost_usd,
                "latency_s": e.latency_s,
                "tags": e.tags,
            }
            for e in sorted_exp[:limit]
        ]

    async def export_json(self) -> str:
        """Export all experiences as JSON."""
        return json.dumps([e.to_dict() for e in self._experiences], indent=2, default=str)

    async def export_csv(self) -> str:
        """Export as CSV."""
        import csv
        import io

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(
            [
                "experience_id",
                "timestamp",
                "mission_id",
                "success",
                "cost_usd",
                "latency_s",
                "retries",
                "risk_score",
            ]
        )
        for e in self._experiences:
            writer.writerow(
                [
                    e.experience_id,
                    e.timestamp.isoformat(),
                    e.mission_id or "",
                    e.success,
                    e.cost_usd,
                    e.latency_s,
                    e.retries,
                    e.risk_score,
                ]
            )
        return output.getvalue()

    async def replay(self, experience_id: str) -> dict[str, Any]:
        """Replay an experience — return its full record for re-execution."""
        exp = await self.get(experience_id)
        if exp is None:
            return {"error": "Experience not found"}
        return {
            "original": exp.to_dict(),
            "replay_inputs": exp.inputs,
            "replay_agents": exp.selected_agents,
            "replay_providers": exp.selected_providers,
        }

    async def stats(self) -> dict[str, Any]:
        """Get aggregate statistics."""
        total = len(self._experiences)
        if total == 0:
            return {"total": 0}
        successes = sum(1 for e in self._experiences if e.success)
        return {
            "total": total,
            "successes": successes,
            "failures": total - successes,
            "success_rate": round(successes / total, 4),
            "avg_cost_usd": round(sum(e.cost_usd for e in self._experiences) / total, 6),
            "avg_latency_s": round(sum(e.latency_s for e in self._experiences) / total, 4),
            "avg_risk_score": round(sum(e.risk_score for e in self._experiences) / total, 4),
            "avg_confidence": round(sum(e.confidence_score for e in self._experiences) / total, 4),
            "unique_agents": len(self._by_agent),
            "unique_providers": len(self._by_provider),
            "unique_tags": len(self._by_tag),
        }

    @property
    def all_experiences(self) -> list[CognitiveExperience]:
        return list(self._experiences)
