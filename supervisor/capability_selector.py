"""Capability Selector — scores and picks agents from the registry.

Given a step with a capability requirement, the Capability Selector:
  1. Queries the Agent Registry for healthy agents that advertise that capability
  2. Scores each candidate:
     - Track record success rate (40%)
     - Current load (20%)
     - Estimated cost (20%)
     - Estimated latency (15%)
     - User preference override (5%)
  3. Picks the highest-scoring agent
  4. Logs the selection reasoning

The Supervisor never calls agents by name — it always goes through the
Capability Selector.
"""

from __future__ import annotations

from core.logging import get_logger
from services.agent_registry import AgentRegistry, AgentSummary, AgentSummaryHealth

_log = get_logger(__name__)

__all__ = ["CapabilitySelector", "SelectionResult", "NoCandidateError"]


class NoCandidateError(RuntimeError):
    """Raised when no agent can handle the requested capability."""

    def __init__(self, capability: str) -> None:
        super().__init__(f"No healthy agent advertises capability: {capability}")
        self.capability = capability


class SelectionResult:
    """The result of a capability selection."""

    def __init__(
        self,
        agent_id: str,
        score: float,
        score_breakdown: dict[str, float],
        candidates: list[AgentSummary],
    ) -> None:
        self.agent_id = agent_id
        self.score = score
        self.score_breakdown = score_breakdown
        self.candidates = candidates

    def __repr__(self) -> str:
        return f"SelectionResult(agent_id={self.agent_id!r}, score={self.score:.3f})"


class CapabilitySelector:
    """Selects the best agent for a capability.

    Scoring weights (configurable):
      - track_record: 0.40 (success rate from the registry's track record)
      - load: 0.20 (fewer in-flight tasks = higher score)
      - cost: 0.20 (lower cost = higher score)
      - latency: 0.15 (lower latency = higher score)
      - user_preference: 0.05 (pinned agent gets a boost)
    """

    def __init__(
        self,
        registry: AgentRegistry,
        *,
        weights: dict[str, float] | None = None,
        user_preferences: dict[str, str] | None = None,
    ) -> None:
        self._registry = registry
        self._weights = weights or {
            "track_record": 0.40,
            "load": 0.20,
            "cost": 0.20,
            "latency": 0.15,
            "user_preference": 0.05,
        }
        # user_preferences: capability_namespace -> agent_id (pinned)
        self._user_preferences: dict[str, str] = user_preferences or {}

    def pin_agent(self, capability: str, agent_id: str) -> None:
        """Pin a specific agent for a capability (user preference)."""
        self._user_preferences[capability] = agent_id

    def unpin(self, capability: str) -> bool:
        """Remove a user preference pin. Returns True if found."""
        return self._user_preferences.pop(capability, None) is not None

    def select(self, capability: str) -> SelectionResult:
        """Select the best agent for ``capability``.

        Raises NoCandidateError if no healthy agent advertises the capability.
        """
        candidates = self._registry.find_by_capability(capability)
        # Filter to healthy agents only
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

        # Score each candidate
        best_score = -1.0
        best_agent: AgentSummary | None = None
        best_breakdown: dict[str, float] = {}

        for candidate in healthy:
            breakdown = self._score(candidate, capability)
            total = sum(breakdown.values())
            if total > best_score:
                best_score = total
                best_agent = candidate
                best_breakdown = breakdown

        assert best_agent is not None
        _log.info(
            "capability_selector.selected",
            capability=capability,
            agent_id=best_agent.agent_id,
            score=round(best_score, 4),
            candidates=len(healthy),
        )
        return SelectionResult(
            agent_id=best_agent.agent_id,
            score=best_score,
            score_breakdown=best_breakdown,
            candidates=healthy,
        )

    def _score(self, candidate: AgentSummary, capability: str) -> dict[str, float]:
        """Score a single candidate. Returns a dict of weighted scores."""
        breakdown: dict[str, float] = {}

        # Track record (success rate)
        success_rate = candidate.track_record.get("success_rate", 1.0)
        breakdown["track_record"] = success_rate * self._weights["track_record"]

        # Load (inverse of in-flight count — we don't have real in-flight data,
        # so we use the number of capabilities as a proxy for complexity)
        # Lower complexity = higher score
        load_factor = 1.0 / max(1, len(candidate.capabilities))
        breakdown["load"] = load_factor * self._weights["load"]

        # Cost (inverse — lower cost = higher score)
        avg_cost = candidate.track_record.get("avg_cost_usd", 0.0)
        if avg_cost > 0:
            cost_factor = 1.0 / (1.0 + avg_cost * 100)  # sigmoid-like
        else:
            cost_factor = 1.0  # free (local models)
        breakdown["cost"] = cost_factor * self._weights["cost"]

        # Latency (inverse — lower latency = higher score)
        avg_latency = candidate.track_record.get("avg_latency_ms", 1000.0)
        latency_factor = 1.0 / (1.0 + avg_latency / 1000.0)
        breakdown["latency"] = latency_factor * self._weights["latency"]

        # User preference
        pinned = self._user_preferences.get(capability)
        if pinned and pinned == candidate.agent_id:
            breakdown["user_preference"] = self._weights["user_preference"]
        else:
            breakdown["user_preference"] = 0.0

        return breakdown
