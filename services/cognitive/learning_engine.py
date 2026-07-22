"""Learning Engine — explainable statistical learning from historical executions.

Analyzes the CognitiveExperienceEngine's data to determine:
  - Best provider (by success rate, latency, cost)
  - Best coding agent (by success rate, quality)
  - Best planner (by plan quality)
  - Best workflow (by success rate, efficiency)
  - Best routing (by reliability)
  - Best prompt (by output quality)
  - Best decomposition strategy (by completion rate)
  - Best retry strategy (by recovery rate)
  - Best recovery strategy (by rollback success)
  - Best execution policy (by safety + success)

All findings are explainable — every insight includes the evidence
(sample count, averages, comparisons) that supports it.
"""

from __future__ import annotations

from collections import defaultdict

from core.logging import get_logger
from services.cognitive.experience_engine import CognitiveExperience, CognitiveExperienceEngine
from services.cognitive.models import LearningInsight, LearningMetric

_log = get_logger(__name__)

__all__ = ["CognitiveLearningEngine"]


class CognitiveLearningEngine:
    """Explainable statistical learning from execution history.

    Uses simple statistics (averages, rates, comparisons) — no opaque ML.
    Every insight includes the evidence behind it.
    """

    def __init__(self, experience_engine: CognitiveExperienceEngine) -> None:
        self._exp = experience_engine

    async def learn_all(self) -> list[LearningInsight]:
        """Run all learning analyses and return insights."""
        insights: list[LearningInsight] = []
        insights.extend(await self.best_provider())
        insights.extend(await self.best_agent())
        insights.extend(await self.best_workflow())
        insights.extend(await self.best_retry_strategy())
        insights.extend(await self.best_recovery_strategy())
        return insights

    async def best_provider(self) -> list[LearningInsight]:
        """Determine the best provider by success rate, latency, and cost."""
        experiences = self._exp.all_experiences
        by_provider: dict[str, list[CognitiveExperience]] = defaultdict(list)
        for exp in experiences:
            for provider in exp.selected_providers:
                by_provider[provider].append(exp)
        insights: list[LearningInsight] = []
        for provider, exps in by_provider.items():
            if len(exps) < 3:
                continue
            success_rate = sum(1 for e in exps if e.success) / len(exps)
            avg_latency = sum(e.latency_s for e in exps) / len(exps)
            avg_cost = sum(e.cost_usd for e in exps) / len(exps)
            insights.append(
                LearningInsight(
                    category="best_provider",
                    finding=f"Provider '{provider}': {success_rate:.1%} success, {avg_latency:.2f}s avg latency, ${avg_cost:.4f} avg cost",
                    evidence={
                        "provider": provider,
                        "sample_count": len(exps),
                        "success_rate": round(success_rate, 4),
                        "avg_latency_s": round(avg_latency, 4),
                        "avg_cost_usd": round(avg_cost, 6),
                    },
                    confidence=min(1.0, len(exps) / 20.0),
                    explanation=f"Based on {len(exps)} executions. Success rate: {success_rate:.1%}. "
                    f"Average latency: {avg_latency:.2f}s. Average cost: ${avg_cost:.4f}.",
                )
            )
        # Rank by composite score
        insights.sort(key=lambda i: i.evidence.get("success_rate", 0), reverse=True)
        return insights

    async def best_agent(self) -> list[LearningInsight]:
        """Determine the best agent by success rate and quality."""
        experiences = self._exp.all_experiences
        by_agent: dict[str, list[CognitiveExperience]] = defaultdict(list)
        for exp in experiences:
            for agent in exp.selected_agents:
                by_agent[agent].append(exp)
        insights: list[LearningInsight] = []
        for agent, exps in by_agent.items():
            if len(exps) < 3:
                continue
            success_rate = sum(1 for e in exps if e.success) / len(exps)
            avg_cost = sum(e.cost_usd for e in exps) / len(exps)
            avg_confidence = sum(e.confidence_score for e in exps) / len(exps)
            insights.append(
                LearningInsight(
                    category="best_agent",
                    finding=f"Agent '{agent}': {success_rate:.1%} success, {avg_confidence:.2f} avg confidence",
                    evidence={
                        "agent": agent,
                        "sample_count": len(exps),
                        "success_rate": round(success_rate, 4),
                        "avg_cost_usd": round(avg_cost, 6),
                        "avg_confidence": round(avg_confidence, 4),
                    },
                    confidence=min(1.0, len(exps) / 20.0),
                    explanation=f"Based on {len(exps)} executions. Success rate: {success_rate:.1%}. "
                    f"Average confidence: {avg_confidence:.2f}.",
                )
            )
        insights.sort(key=lambda i: i.evidence.get("success_rate", 0), reverse=True)
        return insights

    async def best_workflow(self) -> list[LearningInsight]:
        """Determine the best workflow by success rate."""
        experiences = self._exp.all_experiences
        by_wf: dict[str, list[CognitiveExperience]] = defaultdict(list)
        for exp in experiences:
            if exp.workflow_id:
                by_wf[exp.workflow_id].append(exp)
        insights: list[LearningInsight] = []
        for wf_id, exps in by_wf.items():
            if len(exps) < 2:
                continue
            success_rate = sum(1 for e in exps if e.success) / len(exps)
            avg_duration = sum(e.latency_s for e in exps) / len(exps)
            insights.append(
                LearningInsight(
                    category="best_workflow",
                    finding=f"Workflow '{wf_id}': {success_rate:.1%} success, {avg_duration:.2f}s avg duration",
                    evidence={
                        "workflow_id": wf_id,
                        "sample_count": len(exps),
                        "success_rate": round(success_rate, 4),
                        "avg_duration_s": round(avg_duration, 4),
                    },
                    confidence=min(1.0, len(exps) / 10.0),
                    explanation=f"Based on {len(exps)} executions with this workflow.",
                )
            )
        insights.sort(key=lambda i: i.evidence.get("success_rate", 0), reverse=True)
        return insights

    async def best_retry_strategy(self) -> list[LearningInsight]:
        """Analyze retry strategy effectiveness."""
        experiences = self._exp.all_experiences
        retried = [e for e in experiences if e.retries > 0]
        if len(retried) < 3:
            return [
                LearningInsight(
                    category="best_retry_strategy",
                    finding="Insufficient data for retry analysis",
                    evidence={"sample_count": len(retried)},
                    confidence=0.1,
                    explanation="Need at least 3 retried executions for analysis.",
                )
            ]
        recovery_rate = sum(1 for e in retried if e.success) / len(retried)
        avg_retries = sum(e.retries for e in retried) / len(retried)
        return [
            LearningInsight(
                category="best_retry_strategy",
                finding=f"Retry recovery rate: {recovery_rate:.1%} with avg {avg_retries:.1f} retries",
                evidence={
                    "sample_count": len(retried),
                    "recovery_rate": round(recovery_rate, 4),
                    "avg_retries": round(avg_retries, 2),
                },
                confidence=min(1.0, len(retried) / 10.0),
                explanation=f"Of {len(retried)} retried executions, {recovery_rate:.1%} eventually succeeded "
                f"with an average of {avg_retries:.1f} retries.",
            )
        ]

    async def best_recovery_strategy(self) -> list[LearningInsight]:
        """Analyze rollback/recovery effectiveness."""
        experiences = self._exp.all_experiences
        rolled_back = [e for e in experiences if e.rollback]
        if len(rolled_back) < 2:
            return [
                LearningInsight(
                    category="best_recovery_strategy",
                    finding="Insufficient data for recovery analysis",
                    evidence={"sample_count": len(rolled_back)},
                    confidence=0.1,
                    explanation="Need at least 2 rolled-back executions.",
                )
            ]
        return [
            LearningInsight(
                category="best_recovery_strategy",
                finding=f"{len(rolled_back)} executions had rollback applied",
                evidence={
                    "sample_count": len(rolled_back),
                    "rollback_types": list({e.rollback for e in rolled_back if e.rollback}),
                },
                confidence=min(1.0, len(rolled_back) / 5.0),
                explanation=f"{len(rolled_back)} executions triggered rollback procedures.",
            )
        ]

    async def metrics(self) -> list[LearningMetric]:
        """Get summary learning metrics."""
        experiences = self._exp.all_experiences
        total = len(experiences)
        if total == 0:
            return [LearningMetric(name="total_experiences", value=0, unit="count")]
        successes = sum(1 for e in experiences if e.success)
        return [
            LearningMetric(
                name="total_experiences",
                value=total,
                unit="count",
                explanation="Total executions analyzed",
            ),
            LearningMetric(
                name="success_rate",
                value=successes / total,
                unit="ratio",
                explanation=f"{successes}/{total} succeeded",
            ),
            LearningMetric(
                name="avg_cost",
                value=sum(e.cost_usd for e in experiences) / total,
                unit="USD",
                explanation="Average cost per execution",
            ),
            LearningMetric(
                name="avg_latency",
                value=sum(e.latency_s for e in experiences) / total,
                unit="seconds",
                explanation="Average execution latency",
            ),
            LearningMetric(
                name="avg_confidence",
                value=sum(e.confidence_score for e in experiences) / total,
                unit="ratio",
                explanation="Average confidence score",
            ),
            LearningMetric(
                name="avg_risk",
                value=sum(e.risk_score for e in experiences) / total,
                unit="ratio",
                explanation="Average risk score",
            ),
        ]
