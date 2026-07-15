"""AdaptiveRouter — self-improving routing that learns from execution history.

Replaces the v1.0 CapabilitySelector's static weights (40/20/20/15/5) with
dynamic weights that adapt based on execution outcomes.

Learning loop:
1. After every step, ExecutionHistory records the outcome
2. Every N executions (default 50), the router recomputes agent scores
3. Weights are adjusted based on:
   - Recent success rate (higher success → higher weight)
   - Recent cost (lower cost → higher weight)
   - Recent latency (lower latency → higher weight)
   - Correction rate (fewer corrections → higher weight)
4. Weight changes are logged for auditability

The router falls back to v1.0 static weights when there's insufficient
history (fewer than min_samples executions for a capability).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from core.logging import get_logger
from services.agent_registry import AgentRegistry, AgentSummary, AgentSummaryHealth
from supervisor.capability_selector import CapabilitySelector, NoCandidateError, SelectionResult
from supervisor.v2.execution_history import ExecutionHistory

_log = get_logger(__name__)

__all__ = ["AdaptiveRouter", "RouterWeights", "WeightAdjustment"]


@dataclass
class RouterWeights:
    """Dynamic routing weights for a capability namespace."""

    capability: str
    success_weight: float = 0.40
    cost_weight: float = 0.20
    latency_weight: float = 0.15
    correction_weight: float = 0.15
    load_weight: float = 0.05
    user_pref_weight: float = 0.05
    last_updated: float = 0.0  # timestamp
    sample_count: int = 0
    adjustments: list[WeightAdjustment] = field(default_factory=list)


@dataclass
class WeightAdjustment:
    """A recorded weight adjustment for auditability."""

    timestamp: float
    capability: str
    old_weights: dict[str, float]
    new_weights: dict[str, float]
    reason: str


class AdaptiveRouter(CapabilitySelector):
    """Capability selector that learns from execution history.

    Extends the v1.0 CapabilitySelector with adaptive weight tuning.
    When there's insufficient history, it falls back to the v1.0 static
    weights (40/20/20/15/5).
    """

    def __init__(
        self,
        registry: AgentRegistry,
        history: ExecutionHistory,
        *,
        min_samples: int = 10,
        recompute_interval: int = 50,
        user_preferences: dict[str, str] | None = None,
    ) -> None:
        super().__init__(registry=registry, user_preferences=user_preferences)
        self._history = history
        self._min_samples = min_samples
        self._recompute_interval = recompute_interval
        self._execution_count: int = 0
        self._weights: dict[str, RouterWeights] = {}  # type: ignore[assignment]
        self._adjustments: list[WeightAdjustment] = []

    def select(self, capability: str) -> SelectionResult:
        """Select the best agent for a capability using adaptive weights."""
        candidates = self._registry.find_by_capability(capability)
        healthy = [
            c
            for c in candidates
            if c.health in (AgentSummaryHealth.HEALTHY, AgentSummaryHealth.DEGRADED)
            and c.initialized
        ]
        if not healthy:
            raise NoCandidateError(capability)

        if len(healthy) == 1:
            return SelectionResult(
                agent_id=healthy[0].agent_id,
                score=1.0,
                score_breakdown={"single_candidate": 1.0},
                candidates=healthy,
            )

        # Get or create weights for this capability
        weights = self._get_weights(capability)

        # Score each candidate using adaptive weights
        best_score = -1.0
        best_agent: AgentSummary | None = None
        best_breakdown: dict[str, float] = {}

        for candidate in healthy:
            breakdown = self._score_adaptive(candidate, capability, weights)
            total = sum(breakdown.values())
            if total > best_score:
                best_score = total
                best_agent = candidate
                best_breakdown = breakdown

        assert best_agent is not None
        _log.info(
            "adaptive_router.selected",
            capability=capability,
            agent_id=best_agent.agent_id,
            score=round(best_score, 4),
            candidates=len(healthy),
            weights=weights.__dict__ if weights.sample_count >= self._min_samples else "static",
        )
        return SelectionResult(
            agent_id=best_agent.agent_id,
            score=best_score,
            score_breakdown=best_breakdown,
            candidates=healthy,
        )

    def record_execution(self, capability: str) -> None:
        """Called after every step execution. Triggers recompute if needed."""
        self._execution_count += 1
        if self._execution_count % self._recompute_interval == 0:
            self._recompute_weights(capability)

    def get_weights(self, capability: str) -> RouterWeights | None:
        """Return the current weights for a capability."""
        return self._weights.get(capability)

    def get_adjustments(self, limit: int = 20) -> list[WeightAdjustment]:
        """Return recent weight adjustments for auditability."""
        return list(reversed(self._adjustments[-limit:]))

    def _get_weights(self, capability: str) -> RouterWeights:
        """Get weights for a capability, creating defaults if needed."""
        if capability not in self._weights:
            self._weights[capability] = RouterWeights(capability=capability)
        return self._weights[capability]

    def _score_adaptive(
        self,
        candidate: AgentSummary,
        capability: str,
        weights: RouterWeights,
    ) -> dict[str, float]:
        """Score a candidate using adaptive (or static) weights."""
        breakdown: dict[str, float] = {}

        # Get agent-specific stats from history
        agent_stats = self._history.get_agent_capability_stats(
            candidate.agent_id,
            capability,
            last_n=50,
        )

        # If insufficient data, use the v1.0 static scoring
        if agent_stats["sample_count"] < self._min_samples:
            return self._score_static(candidate, capability)

        # Adaptive scoring based on real execution data
        success_rate = agent_stats["success_rate"]
        breakdown["success"] = success_rate * weights.success_weight

        # Cost (inverse — lower cost = higher score)
        avg_cost = agent_stats["avg_cost_usd"]
        if avg_cost > 0:
            cost_factor = 1.0 / (1.0 + avg_cost * 100)
        else:
            cost_factor = 1.0
        breakdown["cost"] = cost_factor * weights.cost_weight

        # Latency (inverse — lower latency = higher score)
        avg_latency = agent_stats["avg_latency_ms"]
        latency_factor = 1.0 / (1.0 + avg_latency / 1000.0)
        breakdown["latency"] = latency_factor * weights.latency_weight

        # Correction rate (inverse — fewer corrections = higher score)
        correction_rate = agent_stats["correction_rate"]
        correction_factor = 1.0 - correction_rate
        breakdown["correction"] = correction_factor * weights.correction_weight

        # Load (inverse — fewer capabilities = lighter load)
        load_factor = 1.0 / max(1, len(candidate.capabilities))
        breakdown["load"] = load_factor * weights.load_weight

        # User preference
        pinned = self._user_preferences.get(capability)
        breakdown["user_pref"] = (
            weights.user_pref_weight if pinned and pinned == candidate.agent_id else 0.0
        )

        return breakdown

    def _score_static(
        self,
        candidate: AgentSummary,
        capability: str,
    ) -> dict[str, float]:
        """Fall back to v1.0 static scoring when insufficient history."""
        return self._score(candidate, capability)

    def _recompute_weights(self, capability: str) -> None:
        """Recompute weights for a capability based on recent execution data."""
        import time

        stats = self._history.get_capability_stats(capability, last_n=100)
        if stats["sample_count"] < self._min_samples:
            return  # Not enough data

        weights = self._get_weights(capability)
        old_weights = {
            "success": weights.success_weight,
            "cost": weights.cost_weight,
            "latency": weights.latency_weight,
            "correction": weights.correction_weight,
            "load": weights.load_weight,
            "user_pref": weights.user_pref_weight,
        }

        # Adjust weights based on what matters most for this capability
        # If success rate is low, increase success weight
        if stats["success_rate"] < 0.8:
            weights.success_weight = min(0.60, weights.success_weight + 0.05)
            weights.cost_weight = max(0.10, weights.cost_weight - 0.02)

        # If correction rate is high, increase correction weight
        if stats["correction_rate"] > 0.3:
            weights.correction_weight = min(0.25, weights.correction_weight + 0.05)
            weights.load_weight = max(0.02, weights.load_weight - 0.02)

        # If cost varies a lot, increase cost weight
        if stats["avg_cost_usd"] > 0.05:
            weights.cost_weight = min(0.30, weights.cost_weight + 0.02)

        # If latency is high, increase latency weight
        if stats["p95_latency_ms"] > 5000:
            weights.latency_weight = min(0.25, weights.latency_weight + 0.03)

        # Normalize weights to sum to 1.0
        total = (
            weights.success_weight
            + weights.cost_weight
            + weights.latency_weight
            + weights.correction_weight
            + weights.load_weight
            + weights.user_pref_weight
        )
        if total > 0:
            weights.success_weight /= total
            weights.cost_weight /= total
            weights.latency_weight /= total
            weights.correction_weight /= total
            weights.load_weight /= total
            weights.user_pref_weight /= total

        weights.last_updated = time.time()
        weights.sample_count = int(stats["sample_count"])

        new_weights = {
            "success": weights.success_weight,
            "cost": weights.cost_weight,
            "latency": weights.latency_weight,
            "correction": weights.correction_weight,
            "load": weights.load_weight,
            "user_pref": weights.user_pref_weight,
        }

        adjustment = WeightAdjustment(
            timestamp=weights.last_updated,
            capability=capability,
            old_weights=old_weights,
            new_weights=new_weights,
            reason=f"Auto-adjusted based on {stats['sample_count']} executions "
            f"(success={stats['success_rate']:.1%}, correction={stats['correction_rate']:.1%})",
        )
        self._adjustments.append(adjustment)
        weights.adjustments.append(adjustment)

        _log.info(
            "adaptive_router.weights_adjusted",
            capability=capability,
            old=old_weights,
            new=new_weights,
            reason=adjustment.reason,
        )
