"""Mission Analytics + Search + Export.

Analytics: aggregated metrics across missions (portfolio view).
Search: full-text search over mission titles, descriptions, objectives.
Export: JSON/CSV export of missions + their WBS + decisions.
"""

from __future__ import annotations

import asyncio
import csv
import io
import json
import math
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

from core.logging import get_logger
from services.organization.models import (
    Mission,
    MissionStatus,
)
from services.organization.store import MissionFilter, MissionStore

_log = get_logger(__name__)

__all__ = [
    "MissionAnalytics",
    "MissionExporter",
    "MissionSearchResult",
    "MissionSearcher",
    "PortfolioMetrics",
    "TimelineEntry",
]


_STOP_WORDS = frozenset(
    {
        "a",
        "an",
        "the",
        "and",
        "or",
        "but",
        "is",
        "are",
        "was",
        "were",
        "be",
        "been",
        "being",
        "have",
        "has",
        "had",
        "do",
        "does",
        "did",
        "will",
        "would",
        "could",
        "should",
        "may",
        "might",
        "must",
        "shall",
        "can",
        "of",
        "in",
        "on",
        "at",
        "to",
        "for",
        "with",
        "by",
        "from",
        "as",
        "into",
        "through",
        "this",
        "that",
        "these",
        "those",
    }
)


def _tokenize(text: str) -> list[str]:
    words = re.findall(r"[a-z0-9]+", text.lower())
    return [w for w in words if w not in _STOP_WORDS and len(w) > 1]


@dataclass
class PortfolioMetrics:
    """Portfolio-level metrics across all missions."""

    total_missions: int = 0
    active_missions: int = 0
    completed_missions: int = 0
    failed_missions: int = 0
    cancelled_missions: int = 0
    success_rate: float = 0.0
    total_budget_usd: float = 0.0
    total_spent_usd: float = 0.0
    avg_mission_duration_s: float = 0.0
    avg_completion_pct: float = 0.0
    total_wbs_nodes: int = 0
    total_artifacts: int = 0
    total_decisions: int = 0
    by_priority: dict[str, int] = field(default_factory=dict)
    by_status: dict[str, int] = field(default_factory=dict)
    top_agents: list[dict[str, Any]] = field(default_factory=list)
    top_providers: list[dict[str, Any]] = field(default_factory=list)
    decision_type_counts: dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_missions": self.total_missions,
            "active_missions": self.active_missions,
            "completed_missions": self.completed_missions,
            "failed_missions": self.failed_missions,
            "cancelled_missions": self.cancelled_missions,
            "success_rate": round(self.success_rate, 4),
            "total_budget_usd": round(self.total_budget_usd, 2),
            "total_spent_usd": round(self.total_spent_usd, 2),
            "avg_mission_duration_s": round(self.avg_mission_duration_s, 2),
            "avg_completion_pct": round(self.avg_completion_pct, 2),
            "total_wbs_nodes": self.total_wbs_nodes,
            "total_artifacts": self.total_artifacts,
            "total_decisions": self.total_decisions,
            "by_priority": dict(self.by_priority),
            "by_status": dict(self.by_status),
            "top_agents": list(self.top_agents),
            "top_providers": list(self.top_providers),
            "decision_type_counts": dict(self.decision_type_counts),
        }


@dataclass
class TimelineEntry:
    """A single entry in a mission timeline."""

    timestamp: str
    event_type: str
    description: str
    data: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "event_type": self.event_type,
            "description": self.description,
            "data": dict(self.data),
        }


@dataclass
class MissionSearchResult:
    """A single search result."""

    mission: Mission
    score: float
    matched_terms: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "mission_id": self.mission.mission_id,
            "title": self.mission.title,
            "status": self.mission.status,
            "score": round(self.score, 4),
            "matched_terms": list(self.matched_terms),
            "description": self.mission.description[:200],
        }


class MissionAnalytics:
    """Computes analytics across the mission portfolio.

    All methods are async (the store uses a lock). Returns plain dicts
    so the API can serialize them directly.
    """

    def __init__(self, store: MissionStore) -> None:
        self._store = store

    async def portfolio_metrics(self) -> PortfolioMetrics:
        """Compute portfolio-level metrics."""
        missions = await self._store.all_missions()
        if not missions:
            return PortfolioMetrics()
        total = len(missions)
        by_status: dict[str, int] = defaultdict(int)
        by_priority: dict[str, int] = defaultdict(int)
        for m in missions:
            by_status[m.status] += 1
            by_priority[m.priority] += 1

        completed = by_status.get(MissionStatus.COMPLETED.value, 0)
        failed = by_status.get(MissionStatus.FAILED.value, 0)
        cancelled = by_status.get(MissionStatus.CANCELLED.value, 0)
        terminal = completed + failed + cancelled
        success_rate = completed / terminal if terminal > 0 else 0.0

        durations = [m.elapsed_s() for m in missions if m.started_at]
        avg_duration = sum(durations) / len(durations) if durations else 0.0

        completion_pcts = []
        for m in missions:
            total_nodes = len(m.wbs_nodes)
            if total_nodes > 0:
                completed_nodes = sum(1 for n in m.wbs_nodes if n.status == "succeeded")
                completion_pcts.append(completed_nodes / total_nodes * 100)
        avg_completion = sum(completion_pcts) / len(completion_pcts) if completion_pcts else 0.0

        # Top agents + providers by assignment count
        agent_counts: Counter[str] = Counter()
        provider_counts: Counter[str] = Counter()
        decision_counts: Counter[str] = Counter()
        for m in missions:
            for node in m.wbs_nodes:
                if node.assigned_agent_id:
                    agent_counts[node.assigned_agent_id] += 1
                if node.assigned_provider:
                    provider_counts[node.assigned_provider] += 1
            for d in m.decisions:
                decision_counts[d.decision_type] += 1

        return PortfolioMetrics(
            total_missions=total,
            active_missions=by_status.get(MissionStatus.EXECUTING.value, 0)
            + by_status.get(MissionStatus.PLANNING.value, 0)
            + by_status.get(MissionStatus.READY.value, 0),
            completed_missions=completed,
            failed_missions=failed,
            cancelled_missions=cancelled,
            success_rate=success_rate,
            total_budget_usd=sum(m.budget.total_usd for m in missions),
            total_spent_usd=sum(m.budget.spent_usd for m in missions),
            avg_mission_duration_s=avg_duration,
            avg_completion_pct=avg_completion,
            total_wbs_nodes=sum(len(m.wbs_nodes) for m in missions),
            total_artifacts=sum(len(m.artifacts) for m in missions),
            total_decisions=sum(len(m.decisions) for m in missions),
            by_priority=dict(by_priority),
            by_status=dict(by_status),
            top_agents=[{"agent_id": a, "assignments": c} for a, c in agent_counts.most_common(10)],
            top_providers=[
                {"provider": p, "assignments": c} for p, c in provider_counts.most_common(10)
            ],
            decision_type_counts=dict(decision_counts),
        )

    async def mission_timeline(self, mission: Mission) -> list[TimelineEntry]:
        """Build a timeline of events for a mission."""
        timeline: list[TimelineEntry] = []
        # Creation
        timeline.append(
            TimelineEntry(
                timestamp=mission.created_at.isoformat(),
                event_type="mission_created",
                description=f"Mission '{mission.title}' created",
            )
        )
        # State transitions (inferred from timestamps)
        if mission.started_at:
            timeline.append(
                TimelineEntry(
                    timestamp=mission.started_at.isoformat(),
                    event_type="mission_started",
                    description="Mission execution started",
                )
            )
        if mission.completed_at:
            timeline.append(
                TimelineEntry(
                    timestamp=mission.completed_at.isoformat(),
                    event_type="mission_completed",
                    description=f"Mission reached terminal state: {mission.status}",
                )
            )
        # Decisions
        for d in mission.decisions:
            timeline.append(
                TimelineEntry(
                    timestamp=d.made_at.isoformat(),
                    event_type="decision",
                    description=f"Decision: {d.decision_type} by {d.made_by}",
                    data={"reasoning": d.reasoning, "action": d.action_taken or ""},
                )
            )
        # WBS node completions
        for node in mission.wbs_nodes:
            if node.started_at:
                timeline.append(
                    TimelineEntry(
                        timestamp=node.started_at.isoformat(),
                        event_type="task_started",
                        description=f"Task '{node.title}' started",
                        data={"node_id": node.node_id, "agent_id": node.assigned_agent_id or ""},
                    )
                )
            if node.completed_at:
                timeline.append(
                    TimelineEntry(
                        timestamp=node.completed_at.isoformat(),
                        event_type="task_completed",
                        description=f"Task '{node.title}' {node.status}",
                        data={"node_id": node.node_id, "status": node.status},
                    )
                )
        # Artifacts
        for artifact in mission.artifacts:
            timeline.append(
                TimelineEntry(
                    timestamp=artifact.produced_at.isoformat(),
                    event_type="artifact_produced",
                    description=f"Artifact '{artifact.name}' produced",
                    data={"artifact_id": artifact.artifact_id, "type": artifact.artifact_type},
                )
            )
        # Sort by timestamp
        timeline.sort(key=lambda e: e.timestamp)
        return timeline

    async def mission_graph(self, mission: Mission) -> dict[str, Any]:
        """Build a dependency graph for a mission's WBS."""
        nodes: list[dict[str, Any]] = []
        edges: list[dict[str, Any]] = []
        for node in mission.wbs_nodes:
            nodes.append(
                {
                    "id": node.node_id,
                    "title": node.title,
                    "type": node.node_type,
                    "status": node.status,
                    "parent_id": node.parent_id,
                    "assigned_agent_id": node.assigned_agent_id,
                    "assigned_provider": node.assigned_provider,
                }
            )
            # Parent → child edges
            if node.parent_id:
                edges.append(
                    {
                        "source": node.parent_id,
                        "target": node.node_id,
                        "type": "parent_child",
                    }
                )
            # Dependency edges
            for dep in node.depends_on:
                edges.append(
                    {
                        "source": dep,
                        "target": node.node_id,
                        "type": "dependency",
                    }
                )
        return {
            "mission_id": mission.mission_id,
            "nodes": nodes,
            "edges": edges,
            "node_count": len(nodes),
            "edge_count": len(edges),
        }

    async def success_rate_trend(
        self,
        *,
        days: int = 30,
    ) -> list[dict[str, Any]]:
        """Compute success rate trend over time."""
        missions = await self._store.all_missions()
        now = datetime.now(UTC)
        cutoff = now - timedelta(days=days)
        recent = [m for m in missions if m.created_at >= cutoff]
        if not recent:
            return []
        buckets: dict[str, list[Mission]] = defaultdict(list)
        for m in recent:
            key = m.created_at.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
            buckets[key].append(m)
        series: list[dict[str, Any]] = []
        for key in sorted(buckets.keys()):
            day_missions = buckets[key]
            completed = sum(1 for m in day_missions if m.status == MissionStatus.COMPLETED.value)
            failed = sum(1 for m in day_missions if m.status == MissionStatus.FAILED.value)
            cancelled = sum(1 for m in day_missions if m.status == MissionStatus.CANCELLED.value)
            terminal = completed + failed + cancelled
            success_rate = completed / terminal if terminal > 0 else 0.0
            series.append(
                {
                    "date": key,
                    "total": len(day_missions),
                    "completed": completed,
                    "failed": failed,
                    "cancelled": cancelled,
                    "success_rate": round(success_rate, 4),
                }
            )
        return series


class MissionSearcher:
    """Full-text search over missions.

    Builds a TF-IDF index over mission titles, descriptions, and objectives.
    """

    def __init__(self, store: MissionStore) -> None:
        self._store = store
        self._index: dict[str, list[tuple[str, int]]] = defaultdict(list)
        self._doc_lengths: dict[str, int] = {}
        self._total_docs: int = 0
        self._built = False
        self._lock = asyncio.Lock()

    async def rebuild(self) -> int:
        """Rebuild the search index."""
        missions = await self._store.all_missions()
        async with self._lock:
            self._index.clear()
            self._doc_lengths.clear()
            self._total_docs = len(missions)
            for mission in missions:
                text = " ".join(
                    [
                        mission.title,
                        mission.description,
                        " ".join(mission.objectives),
                        " ".join(mission.deliverables),
                        " ".join(mission.tags),
                    ]
                )
                tokens = _tokenize(text)
                self._doc_lengths[mission.mission_id] = len(tokens)
                tf = Counter(tokens)
                for term, count in tf.items():
                    self._index[term].append((mission.mission_id, count))
            self._built = True
        return self._total_docs

    async def search(
        self,
        query: str,
        *,
        limit: int = 10,
    ) -> list[MissionSearchResult]:
        """Search missions by text query."""
        if not self._built:
            await self.rebuild()
        query_tokens = _tokenize(query)
        if not query_tokens:
            return []
        scores: dict[str, float] = defaultdict(float)
        matched_terms: dict[str, set[str]] = defaultdict(set)
        for term in query_tokens:
            df = len(self._index.get(term, []))
            if df == 0 or self._total_docs == 0:
                continue
            idf = math.log(self._total_docs / df)
            for doc_id, tf in self._index.get(term, []):
                score = tf * idf
                scores[doc_id] += score
                matched_terms[doc_id].add(term)
        for doc_id in scores:
            length = self._doc_lengths.get(doc_id, 1)
            scores[doc_id] /= max(1, length)
        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:limit]
        results: list[MissionSearchResult] = []
        for mission_id, score in ranked:
            try:
                mission = await self._store.get(mission_id)
                results.append(
                    MissionSearchResult(
                        mission=mission,
                        score=score,
                        matched_terms=sorted(matched_terms[mission_id]),
                    )
                )
            except Exception:
                pass
        return results


class MissionExporter:
    """Exports missions to JSON or CSV."""

    def __init__(self, store: MissionStore) -> None:
        self._store = store

    async def export_json(
        self,
        filter: MissionFilter | None = None,
        *,
        limit: int = 1000,
    ) -> str:
        """Export missions as a JSON array string."""
        missions = await self._store.query(filter, limit=limit)
        return json.dumps(
            [m.to_dict() for m in missions],
            indent=2,
            default=str,
        )

    async def export_csv(
        self,
        filter: MissionFilter | None = None,
        *,
        limit: int = 1000,
    ) -> str:
        """Export missions as CSV string."""
        missions = await self._store.query(filter, limit=limit)
        if not missions:
            return ""
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(
            [
                "mission_id",
                "title",
                "status",
                "priority",
                "created_at",
                "started_at",
                "completed_at",
                "budget_total",
                "budget_spent",
                "wbs_nodes",
                "decisions",
                "artifacts",
                "owner",
            ]
        )
        for m in missions:
            writer.writerow(
                [
                    m.mission_id,
                    m.title[:100],
                    m.status,
                    m.priority,
                    m.created_at.isoformat(),
                    m.started_at.isoformat() if m.started_at else "",
                    m.completed_at.isoformat() if m.completed_at else "",
                    m.budget.total_usd,
                    m.budget.spent_usd,
                    len(m.wbs_nodes),
                    len(m.decisions),
                    len(m.artifacts),
                    m.owner or "",
                ]
            )
        return output.getvalue()

    async def export_mission_json(self, mission_id: str) -> str:
        """Export a single mission with full detail as JSON."""
        mission = await self._store.get(mission_id)
        return json.dumps(mission.to_dict(), indent=2, default=str)
