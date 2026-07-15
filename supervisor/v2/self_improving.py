"""SelfImprovingPolicy — the supervisor learns from mistakes.

The policy doesn't modify code — it adjusts routing weights, retry counts,
and escalation thresholds based on execution history.

Adjustments:
- If a capability fails >30% → suggest adding a new agent
- If an agent's correction rate >50% → degrade its score
- If a model is consistently slower for same quality → switch
- If reflection rejects >20% → suggest prompt changes
- If QA fails >10% → suggest success criterion refinement
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from core.contracts.timestamp import utc_now
from core.logging import get_logger
from supervisor.v2.execution_history import ExecutionHistory

_log = get_logger(__name__)

__all__ = ["PolicyAdjustment", "SelfImprovingPolicy", "PolicySuggestion"]


@dataclass
class PolicyAdjustment:
    """A policy adjustment made by the self-improving policy."""

    timestamp: datetime = field(default_factory=utc_now)
    capability: str = ""
    adjustment_type: str = ""  # weight_change, retry_change, threshold_change
    old_value: Any = None
    new_value: Any = None
    reason: str = ""
    evidence: dict[str, Any] = field(default_factory=dict)


@dataclass
class PolicySuggestion:
    """A suggestion for the user (not auto-applied)."""

    timestamp: datetime = field(default_factory=utc_now)
    category: str = ""  # add_agent, change_prompt, refine_criterion, switch_model
    capability: str = ""
    message: str = ""
    evidence: dict[str, Any] = field(default_factory=dict)
    severity: str = "info"  # info, warning, critical


class SelfImprovingPolicy:
    """Policy engine that adapts based on execution history.

    Runs periodically (default every 5 minutes or after every 100 executions)
    and adjusts:
    - Retry counts per capability (more retries for flaky capabilities)
    - Correction attempt limits (more attempts for complex capabilities)
    - Escalation thresholds (when to pause and ask the user)
    - Routing weight suggestions

    Suggestions that require human action (add agent, change prompt) are
    surfaced to the dashboard, not auto-applied.
    """

    # Thresholds
    FAILURE_RATE_THRESHOLD = 0.30  # >30% failure → suggest new agent
    CORRECTION_RATE_THRESHOLD = 0.50  # >50% correction → degrade agent
    REFLECTION_REJECT_RATE = 0.20  # >20% rejection → suggest prompt change
    QA_FAIL_RATE = 0.10  # >10% QA fail → suggest criterion refinement
    SLOW_LATENCY_MS = 10000  # >10s p95 → suggest model switch

    def __init__(
        self,
        history: ExecutionHistory,
        *,
        min_samples: int = 20,
        review_interval: int = 100,
    ) -> None:
        self._history = history
        self._min_samples = min_samples
        self._review_interval = review_interval
        self._execution_count = 0
        self._adjustments: list[PolicyAdjustment] = []
        self._suggestions: list[PolicySuggestion] = []

        # Dynamic policy values (adjustable)
        self._retry_overrides: dict[str, int] = {}  # capability → max retries
        self._correction_overrides: dict[str, int] = {}  # capability → max corrections
        self._degraded_agents: set[str] = set()

    def record_execution(self) -> None:
        """Called after every execution. Triggers review if needed."""
        self._execution_count += 1
        if self._execution_count % self._review_interval == 0:
            self.review()

    def review(self) -> list[PolicySuggestion]:
        """Review execution history and make adjustments/suggestions.

        Returns new suggestions generated during this review.
        """
        new_suggestions: list[PolicySuggestion] = []

        # Get all capabilities that have been executed
        capabilities = self._get_all_capabilities()

        for cap in capabilities:
            stats = self._history.get_capability_stats(cap, last_n=100)
            if stats["sample_count"] < self._min_samples:
                continue

            # Check failure rate
            if stats["success_rate"] < 1.0 - self.FAILURE_RATE_THRESHOLD:
                suggestion = PolicySuggestion(
                    category="add_agent",
                    capability=cap,
                    message=f'Capability "{cap}" has a {1 - stats["success_rate"]:.0%} failure rate '
                    f"({stats['sample_count']} executions). "
                    f"Consider adding another agent that advertises this capability.",
                    evidence=stats,
                    severity="warning",
                )
                self._suggestions.append(suggestion)
                new_suggestions.append(suggestion)

            # Check correction rate
            if stats["correction_rate"] > self.CORRECTION_RATE_THRESHOLD:
                # Auto-adjust: increase max corrections for this capability
                old_max = self._correction_overrides.get(cap, 3)
                new_max = min(5, old_max + 1)
                if new_max > old_max:
                    adjustment = PolicyAdjustment(
                        capability=cap,
                        adjustment_type="correction_limit_increase",
                        old_value=old_max,
                        new_value=new_max,
                        reason=f"Correction rate {stats['correction_rate']:.0%} > {self.CORRECTION_RATE_THRESHOLD:.0%} threshold",
                        evidence=stats,
                    )
                    self._adjustments.append(adjustment)
                    self._correction_overrides[cap] = new_max
                    _log.info(
                        "self_improving.adjusted",
                        capability=cap,
                        adjustment="correction_limit",
                        old=old_max,
                        new=new_max,
                    )

            # Check QA fail rate
            if 1.0 - stats["qa_pass_rate"] > self.QA_FAIL_RATE:
                suggestion = PolicySuggestion(
                    category="refine_criterion",
                    capability=cap,
                    message=f'Capability "{cap}" has a {1 - stats["qa_pass_rate"]:.0%} QA failure rate. '
                    f"Consider refining the success criteria for steps using this capability.",
                    evidence=stats,
                    severity="info",
                )
                self._suggestions.append(suggestion)
                new_suggestions.append(suggestion)

            # Check latency
            if stats["p95_latency_ms"] > self.SLOW_LATENCY_MS:
                suggestion = PolicySuggestion(
                    category="switch_model",
                    capability=cap,
                    message=f'Capability "{cap}" has p95 latency of {stats["p95_latency_ms"]:.0f}ms. '
                    f"Consider switching to a faster model for this capability.",
                    evidence=stats,
                    severity="info",
                )
                self._suggestions.append(suggestion)
                new_suggestions.append(suggestion)

            # Check if we should increase retries for flaky capabilities
            if 0.1 < (1.0 - stats["success_rate"]) < self.FAILURE_RATE_THRESHOLD:
                old_retries = self._retry_overrides.get(cap, 3)
                new_retries = min(5, old_retries + 1)
                if new_retries > old_retries:
                    adjustment = PolicyAdjustment(
                        capability=cap,
                        adjustment_type="retry_increase",
                        old_value=old_retries,
                        new_value=new_retries,
                        reason=f"Moderate failure rate ({1 - stats['success_rate']:.0%}) — increasing retries",
                        evidence=stats,
                    )
                    self._adjustments.append(adjustment)
                    self._retry_overrides[cap] = new_retries
                    _log.info(
                        "self_improving.adjusted",
                        capability=cap,
                        adjustment="retry_limit",
                        old=old_retries,
                        new=new_retries,
                    )

        if new_suggestions:
            _log.info(
                "self_improving.review_complete",
                suggestions=len(new_suggestions),
                total_suggestions=len(self._suggestions),
                total_adjustments=len(self._adjustments),
            )

        return new_suggestions

    def get_retry_limit(self, capability: str, default: int = 3) -> int:
        """Return the retry limit for a capability (may be overridden)."""
        return self._retry_overrides.get(capability, default)

    def get_correction_limit(self, capability: str, default: int = 3) -> int:
        """Return the correction attempt limit for a capability."""
        return self._correction_overrides.get(capability, default)

    def is_agent_degraded(self, agent_id: str) -> bool:
        """Return True if an agent has been degraded by the policy."""
        return agent_id in self._degraded_agents

    def degrade_agent(self, agent_id: str, reason: str) -> None:
        """Degrade an agent (reduces its routing score)."""
        self._degraded_agents.add(agent_id)
        _log.warning(
            "self_improving.agent_degraded",
            agent_id=agent_id,
            reason=reason,
        )

    def get_suggestions(self, *, unresolved_only: bool = True) -> list[PolicySuggestion]:
        """Return policy suggestions (for dashboard)."""
        return list(self._suggestions)

    def get_adjustments(self, limit: int = 50) -> list[PolicyAdjustment]:
        """Return recent policy adjustments (for audit log)."""
        return list(reversed(self._adjustments[-limit:]))

    def _get_all_capabilities(self) -> list[str]:
        """Return all capabilities that have execution history."""
        # This would query the ExecutionHistory's internal index
        # For now, we return from the history's by_capability dict
        return list(self._history._by_capability.keys())  # noqa: SLF001
