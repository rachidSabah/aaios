"""Experience Analyzer + Scorer — pattern discovery + reliability scoring.

The Analyzer mines the experience store for patterns:
  - Successful/failed workflows
  - Repeated failures + repeated fixes
  - Provider/agent reliability
  - Routing/planning/execution quality

The Scorer computes per-agent, per-provider, per-capability reliability
scores (0.0-1.0) from historical evidence. These scores feed the
adaptive router.
"""

from __future__ import annotations

import asyncio
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

from core.logging import get_logger
from services.experience.models import ExperienceRecord
from services.experience.store import ExperienceFilter, ExperienceStore

_log = get_logger(__name__)

__all__ = [
    "AgentReliability",
    "CapabilityReliability",
    "ExperienceAnalyzer",
    "ExperienceScorer",
    "FailurePattern",
    "LearningStats",
    "PatternReport",
    "ProviderReliability",
    "SuccessPattern",
]


@dataclass
class AgentReliability:
    """Reliability score for an agent."""

    agent_id: str
    agent_type: str
    experience_count: int = 0
    success_count: int = 0
    failure_count: int = 0
    success_rate: float = 0.0
    avg_quality: float = 0.0
    avg_latency_s: float = 0.0
    avg_cost_usd: float = 0.0
    avg_retries: float = 0.0
    reliability_score: float = 0.0  # 0.0-1.0
    recent_success_rate: float = 0.0  # last 10 experiences
    trend: str = "stable"  # improving, declining, stable

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "agent_type": self.agent_type,
            "experience_count": self.experience_count,
            "success_count": self.success_count,
            "failure_count": self.failure_count,
            "success_rate": round(self.success_rate, 4),
            "avg_quality": round(self.avg_quality, 4),
            "avg_latency_s": round(self.avg_latency_s, 4),
            "avg_cost_usd": round(self.avg_cost_usd, 6),
            "avg_retries": round(self.avg_retries, 4),
            "reliability_score": round(self.reliability_score, 4),
            "recent_success_rate": round(self.recent_success_rate, 4),
            "trend": self.trend,
        }


@dataclass
class ProviderReliability:
    """Reliability score for a provider."""

    provider: str
    experience_count: int = 0
    success_count: int = 0
    success_rate: float = 0.0
    avg_latency_s: float = 0.0
    avg_cost_usd: float = 0.0
    total_cost_usd: float = 0.0
    total_tokens: int = 0
    reliability_score: float = 0.0
    avg_retries: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "experience_count": self.experience_count,
            "success_count": self.success_count,
            "success_rate": round(self.success_rate, 4),
            "avg_latency_s": round(self.avg_latency_s, 4),
            "avg_cost_usd": round(self.avg_cost_usd, 6),
            "total_cost_usd": round(self.total_cost_usd, 6),
            "total_tokens": self.total_tokens,
            "reliability_score": round(self.reliability_score, 4),
            "avg_retries": round(self.avg_retries, 4),
        }


@dataclass
class CapabilityReliability:
    """Reliability score for a capability namespace."""

    capability: str
    experience_count: int = 0
    success_count: int = 0
    success_rate: float = 0.0
    avg_quality: float = 0.0
    avg_latency_s: float = 0.0
    best_agent_id: str | None = None
    best_agent_success_rate: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "capability": self.capability,
            "experience_count": self.experience_count,
            "success_count": self.success_count,
            "success_rate": round(self.success_rate, 4),
            "avg_quality": round(self.avg_quality, 4),
            "avg_latency_s": round(self.avg_latency_s, 4),
            "best_agent_id": self.best_agent_id,
            "best_agent_success_rate": round(self.best_agent_success_rate, 4),
        }


@dataclass
class SuccessPattern:
    """A pattern of successful executions."""

    description: str
    agent_id: str
    capability: str
    occurrence_count: int = 0
    avg_quality: float = 0.0
    avg_latency_s: float = 0.0
    avg_cost_usd: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "description": self.description,
            "agent_id": self.agent_id,
            "capability": self.capability,
            "occurrence_count": self.occurrence_count,
            "avg_quality": round(self.avg_quality, 4),
            "avg_latency_s": round(self.avg_latency_s, 4),
            "avg_cost_usd": round(self.avg_cost_usd, 6),
        }


@dataclass
class FailurePattern:
    """A pattern of failed executions."""

    description: str
    failure_reason: str
    agent_id: str | None = None
    capability: str | None = None
    occurrence_count: int = 0
    recovery_action: str | None = None
    recovery_success_rate: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "description": self.description,
            "failure_reason": self.failure_reason,
            "agent_id": self.agent_id,
            "capability": self.capability,
            "occurrence_count": self.occurrence_count,
            "recovery_action": self.recovery_action,
            "recovery_success_rate": round(self.recovery_success_rate, 4),
        }


@dataclass
class LearningStats:
    """Top-level learning statistics."""

    total_experiences: int = 0
    total_successes: int = 0
    total_failures: int = 0
    overall_success_rate: float = 0.0
    overall_avg_quality: float = 0.0
    overall_avg_latency_s: float = 0.0
    overall_avg_cost_usd: float = 0.0
    total_cost_usd: float = 0.0
    total_tokens: int = 0
    agent_count: int = 0
    provider_count: int = 0
    capability_count: int = 0
    workflow_count: int = 0
    last_24h_count: int = 0
    last_7d_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_experiences": self.total_experiences,
            "total_successes": self.total_successes,
            "total_failures": self.total_failures,
            "overall_success_rate": round(self.overall_success_rate, 4),
            "overall_avg_quality": round(self.overall_avg_quality, 4),
            "overall_avg_latency_s": round(self.overall_avg_latency_s, 4),
            "overall_avg_cost_usd": round(self.overall_avg_cost_usd, 6),
            "total_cost_usd": round(self.total_cost_usd, 6),
            "total_tokens": self.total_tokens,
            "agent_count": self.agent_count,
            "provider_count": self.provider_count,
            "capability_count": self.capability_count,
            "workflow_count": self.workflow_count,
            "last_24h_count": self.last_24h_count,
            "last_7d_count": self.last_7d_count,
        }


@dataclass
class PatternReport:
    """Report of discovered patterns."""

    success_patterns: list[SuccessPattern] = field(default_factory=list)
    failure_patterns: list[FailurePattern] = field(default_factory=list)
    repeated_failures: list[FailurePattern] = field(default_factory=list)
    repeated_fixes: list[SuccessPattern] = field(default_factory=list)
    generated_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "success_patterns": [p.to_dict() for p in self.success_patterns],
            "failure_patterns": [p.to_dict() for p in self.failure_patterns],
            "repeated_failures": [p.to_dict() for p in self.repeated_failures],
            "repeated_fixes": [p.to_dict() for p in self.repeated_fixes],
            "generated_at": self.generated_at,
        }


class ExperienceAnalyzer:
    """Mines the experience store for patterns.

    All methods are async (the store uses a lock). Returns plain dicts so
    the API can serialize them directly.
    """

    def __init__(self, store: ExperienceStore) -> None:
        self._store = store

    async def learning_stats(self) -> LearningStats:
        """Compute top-level learning statistics."""
        all_records = await self._store.all_records()
        if not all_records:
            return LearningStats()
        total = len(all_records)
        success_count = sum(1 for r in all_records if r.success)
        now = datetime.now(UTC)
        last_24h = sum(1 for r in all_records if (now - r.timestamp).total_seconds() < 86400)
        last_7d = sum(1 for r in all_records if (now - r.timestamp).total_seconds() < 604800)
        agents = await self._store.list_agents()
        providers = await self._store.list_providers()
        capabilities = await self._store.list_capabilities()
        workflows = {r.workflow_id for r in all_records if r.workflow_id}
        return LearningStats(
            total_experiences=total,
            total_successes=success_count,
            total_failures=total - success_count,
            overall_success_rate=success_count / total,
            overall_avg_quality=sum(r.quality_score() for r in all_records) / total,
            overall_avg_latency_s=sum(r.latency_s for r in all_records) / total,
            overall_avg_cost_usd=sum(r.cost_usd for r in all_records) / total,
            total_cost_usd=sum(r.cost_usd for r in all_records),
            total_tokens=sum(r.token_usage.total_tokens for r in all_records),
            agent_count=len(agents),
            provider_count=len(providers),
            capability_count=len(capabilities),
            workflow_count=len(workflows),
            last_24h_count=last_24h,
            last_7d_count=last_7d,
        )

    async def discover_patterns(self) -> PatternReport:
        """Discover success/failure patterns in the experience store."""
        all_records = await self._store.all_records()
        report = PatternReport(generated_at=datetime.now(UTC).isoformat())
        self._find_success_patterns(all_records, report)
        self._find_failure_patterns(all_records, report)
        self._find_repeated_fixes(all_records, report)
        return report

    @staticmethod
    def _find_success_patterns(
        all_records: list[ExperienceRecord],
        report: PatternReport,
    ) -> None:
        """Find agent+capability combos that consistently succeed."""
        success_by_combo: dict[tuple[str, str], list[ExperienceRecord]] = defaultdict(list)
        for r in all_records:
            if r.success:
                for cap in r.capabilities_used:
                    success_by_combo[(r.agent_id, cap)].append(r)
        for (agent_id, capability), records in success_by_combo.items():
            if len(records) >= 3:
                report.success_patterns.append(SuccessPattern(
                    description=f"Agent '{agent_id}' successfully serves '{capability}'",
                    agent_id=agent_id,
                    capability=capability,
                    occurrence_count=len(records),
                    avg_quality=sum(r.quality_score() for r in records) / len(records),
                    avg_latency_s=sum(r.latency_s for r in records) / len(records),
                    avg_cost_usd=sum(r.cost_usd for r in records) / len(records),
                ))
        report.success_patterns.sort(key=lambda p: p.occurrence_count, reverse=True)

    @staticmethod
    def _find_failure_patterns(
        all_records: list[ExperienceRecord],
        report: PatternReport,
    ) -> None:
        """Find repeated failure patterns."""
        failure_by_reason: dict[tuple[str, str | None], list[ExperienceRecord]] = defaultdict(list)
        for r in all_records:
            if not r.success and r.failure_reason:
                cap = r.capabilities_used[0] if r.capabilities_used else None
                failure_by_reason[(r.failure_reason, cap)].append(r)
        for (reason, cap), records in failure_by_reason.items():
            if len(records) >= 2:
                recovery_actions = [r.recovery_action for r in records if r.recovery_action]
                recovery_success_rate = len(recovery_actions) / len(records) if recovery_actions else 0.0
                report.failure_patterns.append(FailurePattern(
                    description=f"Repeated failure: '{reason[:80]}' on '{cap or 'unknown'}'",
                    failure_reason=reason,
                    agent_id=records[0].agent_id,
                    capability=cap,
                    occurrence_count=len(records),
                    recovery_action=recovery_actions[0] if recovery_actions else None,
                    recovery_success_rate=recovery_success_rate,
                ))
        report.failure_patterns.sort(key=lambda p: p.occurrence_count, reverse=True)
        report.repeated_failures = report.failure_patterns[:5]

    @staticmethod
    def _find_repeated_fixes(
        all_records: list[ExperienceRecord],
        report: PatternReport,
    ) -> None:
        """Find recovery actions that consistently work."""
        fix_by_action: dict[str, list[ExperienceRecord]] = defaultdict(list)
        for r in all_records:
            if r.recovery_action and r.success:
                fix_by_action[r.recovery_action].append(r)
        for action, records in fix_by_action.items():
            if len(records) >= 2:
                report.repeated_fixes.append(SuccessPattern(
                    description=f"Recovery '{action[:80]}' works consistently",
                    agent_id=records[0].agent_id,
                    capability=records[0].capabilities_used[0] if records[0].capabilities_used else "unknown",
                    occurrence_count=len(records),
                    avg_quality=sum(r.quality_score() for r in records) / len(records),
                    avg_latency_s=sum(r.latency_s for r in records) / len(records),
                    avg_cost_usd=sum(r.cost_usd for r in records) / len(records),
                ))
        report.repeated_fixes.sort(key=lambda p: p.occurrence_count, reverse=True)

    async def trend_over_time(
        self,
        *,
        days: int = 30,
        bucket: str = "day",  # "day" or "hour"
    ) -> list[dict[str, Any]]:
        """Compute success rate trend over time."""
        all_records = await self._store.all_records()
        now = datetime.now(UTC)
        cutoff = now - timedelta(days=days)
        recent = [r for r in all_records if r.timestamp >= cutoff]
        if not recent:
            return []
        # Bucket records
        buckets: dict[str, list[ExperienceRecord]] = defaultdict(list)
        for r in recent:
            if bucket == "hour":
                key = r.timestamp.replace(minute=0, second=0, microsecond=0).isoformat()
            else:
                key = r.timestamp.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
            buckets[key].append(r)
        # Compute per-bucket stats
        series: list[dict[str, Any]] = []
        for key in sorted(buckets.keys()):
            records = buckets[key]
            success_count = sum(1 for r in records if r.success)
            series.append({
                "timestamp": key,
                "count": len(records),
                "success_count": success_count,
                "failure_count": len(records) - success_count,
                "success_rate": round(success_count / len(records), 4) if records else 0.0,
                "avg_quality": round(sum(r.quality_score() for r in records) / len(records), 4),
                "avg_latency_s": round(sum(r.latency_s for r in records) / len(records), 4),
            })
        return series


class ExperienceScorer:
    """Computes reliability scores from historical evidence.

    Used by the adaptive router to choose the best agent/provider based
    on accumulated experience.
    """

    def __init__(self, store: ExperienceStore) -> None:
        self._store = store

    async def score_agent(self, agent_id: str) -> AgentReliability:
        """Compute reliability score for an agent."""
        records = await self._store.query(ExperienceFilter(agent_id=agent_id), limit=1000)
        if not records:
            return AgentReliability(agent_id=agent_id, agent_type="unknown")
        total = len(records)
        success_count = sum(1 for r in records if r.success)
        # Recent = last 10 (most recent first since store sorts desc)
        recent = records[:10]
        recent_success = sum(1 for r in recent if r.success)
        recent_rate = recent_success / len(recent) if recent else 0.0
        # Trend: compare recent to overall
        overall_rate = success_count / total
        if recent_rate > overall_rate + 0.1:
            trend = "improving"
        elif recent_rate < overall_rate - 0.1:
            trend = "declining"
        else:
            trend = "stable"
        # Reliability score: weighted combination
        # 50% success rate, 30% quality, 20% recent performance
        avg_quality = sum(r.quality_score() for r in records) / total
        reliability = (
            overall_rate * 0.5
            + avg_quality * 0.3
            + recent_rate * 0.2
        )
        return AgentReliability(
            agent_id=agent_id,
            agent_type=records[0].agent_type,
            experience_count=total,
            success_count=success_count,
            failure_count=total - success_count,
            success_rate=overall_rate,
            avg_quality=avg_quality,
            avg_latency_s=sum(r.latency_s for r in records) / total,
            avg_cost_usd=sum(r.cost_usd for r in records) / total,
            avg_retries=sum(r.retries for r in records) / total,
            reliability_score=reliability,
            recent_success_rate=recent_rate,
            trend=trend,
        )

    async def score_provider(self, provider: str) -> ProviderReliability:
        """Compute reliability score for a provider."""
        records = await self._store.query(ExperienceFilter(provider=provider), limit=1000)
        if not records:
            return ProviderReliability(provider=provider)
        total = len(records)
        success_count = sum(1 for r in records if r.success)
        # Reliability: 60% success, 25% latency (inverted), 15% retry rate (inverted)
        avg_latency = sum(r.latency_s for r in records) / total
        avg_retries = sum(r.retries for r in records) / total
        # Normalize latency: 0-2s → 1.0-0.0
        latency_score = max(0.0, 1.0 - avg_latency / 2.0)
        # Normalize retries: 0-3 → 1.0-0.0
        retry_score = max(0.0, 1.0 - avg_retries / 3.0)
        reliability = (success_count / total) * 0.6 + latency_score * 0.25 + retry_score * 0.15
        return ProviderReliability(
            provider=provider,
            experience_count=total,
            success_count=success_count,
            success_rate=success_count / total,
            avg_latency_s=avg_latency,
            avg_cost_usd=sum(r.cost_usd for r in records) / total,
            total_cost_usd=sum(r.cost_usd for r in records),
            total_tokens=sum(r.token_usage.total_tokens for r in records),
            avg_retries=avg_retries,
            reliability_score=reliability,
        )

    async def score_capability(self, capability: str) -> CapabilityReliability:
        """Compute reliability score for a capability."""
        records = await self._store.query(ExperienceFilter(capability=capability), limit=1000)
        if not records:
            return CapabilityReliability(capability=capability)
        total = len(records)
        success_count = sum(1 for r in records if r.success)
        # Find best agent for this capability
        agent_success: dict[str, list[bool]] = defaultdict(list)
        for r in records:
            agent_success[r.agent_id].append(r.success)
        best_agent = None
        best_rate = 0.0
        for agent_id, successes in agent_success.items():
            rate = sum(1 for s in successes if s) / len(successes)
            if rate > best_rate and len(successes) >= 2:
                best_rate = rate
                best_agent = agent_id
        return CapabilityReliability(
            capability=capability,
            experience_count=total,
            success_count=success_count,
            success_rate=success_count / total,
            avg_quality=sum(r.quality_score() for r in records) / total,
            avg_latency_s=sum(r.latency_s for r in records) / total,
            best_agent_id=best_agent,
            best_agent_success_rate=best_rate,
        )

    async def rank_agents(self, limit: int = 10) -> list[AgentReliability]:
        """Rank all agents by reliability score."""
        agent_ids = await self._store.list_agents()
        scored = await asyncio.gather(*[self.score_agent(a) for a in agent_ids])
        return sorted(scored, key=lambda a: a.reliability_score, reverse=True)[:limit]

    async def rank_providers(self, limit: int = 10) -> list[ProviderReliability]:
        """Rank all providers by reliability score."""
        providers = await self._store.list_providers()
        scored = await asyncio.gather(*[self.score_provider(p) for p in providers])
        return sorted(scored, key=lambda p: p.reliability_score, reverse=True)[:limit]

    async def rank_capabilities(self, limit: int = 20) -> list[CapabilityReliability]:
        """Rank all capabilities by success rate."""
        capabilities = await self._store.list_capabilities()
        scored = await asyncio.gather(*[self.score_capability(c) for c in capabilities])
        return sorted(scored, key=lambda c: c.success_rate, reverse=True)[:limit]

    async def recommend_agent_for_capability(
        self,
        capability: str,
        *,
        min_experiences: int = 2,
    ) -> dict[str, Any] | None:
        """Recommend the best agent for a capability based on history."""
        records = await self._store.query(ExperienceFilter(capability=capability), limit=1000)
        if not records:
            return None
        # Group by agent
        by_agent: dict[str, list[ExperienceRecord]] = defaultdict(list)
        for r in records:
            by_agent[r.agent_id].append(r)
        # Score each
        best_agent = None
        best_score = -1.0
        for agent_id, agent_records in by_agent.items():
            if len(agent_records) < min_experiences:
                continue
            success_rate = sum(1 for r in agent_records if r.success) / len(agent_records)
            avg_quality = sum(r.quality_score() for r in agent_records) / len(agent_records)
            # Lower cost is better
            avg_cost = sum(r.cost_usd for r in agent_records) / len(agent_records)
            cost_score = max(0.0, 1.0 - avg_cost / 0.10)  # normalize: $0.10 = max
            score = success_rate * 0.5 + avg_quality * 0.3 + cost_score * 0.2
            if score > best_score:
                best_score = score
                best_agent = agent_id
        if best_agent is None:
            return None
        best_records = by_agent[best_agent]
        return {
            "capability": capability,
            "recommended_agent_id": best_agent,
            "score": round(best_score, 4),
            "experience_count": len(best_records),
            "success_rate": round(sum(1 for r in best_records if r.success) / len(best_records), 4),
            "avg_quality": round(sum(r.quality_score() for r in best_records) / len(best_records), 4),
            "avg_cost_usd": round(sum(r.cost_usd for r in best_records) / len(best_records), 6),
            "reason": f"Highest composite score from {len(best_records)} past experiences",
        }
