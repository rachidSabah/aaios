"""Executive Intelligence Engine — computes 12 health dimensions + enterprise score.

Continuously calculates operational health, mission health, agent/provider
efficiency, workflow quality, execution success, risk level, reliability,
cost efficiency, learning velocity, and innovation score — combining them
into a single enterprise health score (0.0-1.0) with a letter grade.
"""

from __future__ import annotations

from core.logging import get_logger
from services.intelligence.models import (
    ComponentHealth,
    EnterpriseHealthScore,
    OperationalMetrics,
)

_log = get_logger(__name__)

__all__ = ["ExecutiveIntelligenceEngine"]


class ExecutiveIntelligenceEngine:
    """Computes enterprise health scores from operational metrics.

    The engine is stateless — it takes operational metrics + optional
    historical data and returns a health score. The IntelligenceManager
    is responsible for collecting the metrics.
    """

    def compute_health(
        self,
        metrics: OperationalMetrics,
        *,
        success_rate_history: list[float] | None = None,
        cost_history: list[float] | None = None,
        learning_rate: float = 0.0,
    ) -> EnterpriseHealthScore:
        """Compute the enterprise health score from operational metrics."""
        score = EnterpriseHealthScore()

        # 1. Operational health: uptime, queue depth, event throughput
        score.operational = self._compute_operational_health(metrics)

        # 2. Mission health: completion percentage, active vs total
        score.mission = self._compute_mission_health(metrics)

        # 3. Agent efficiency: reliability x activity
        score.agent_efficiency = self._compute_agent_efficiency(metrics)

        # 4. Provider efficiency: reliability
        score.provider_efficiency = self._compute_provider_efficiency(metrics)

        # 5. Workflow quality: WBS completion ratio
        score.workflow_quality = self._compute_workflow_quality(metrics)

        # 6. Execution success: from history or default
        score.execution_success = self._compute_execution_success(metrics, success_rate_history)

        # 7. Risk level: inverse of open risks (higher = lower risk)
        score.risk_level = self._compute_risk_level(metrics)

        # 8. Reliability: average of agent + provider reliability
        score.reliability = self._compute_reliability(metrics)

        # 9. Cost efficiency: budget utilization (lower = better)
        score.cost_efficiency = self._compute_cost_efficiency(metrics, cost_history)

        # 10. Learning velocity: experiences collected rate
        score.learning_velocity = self._compute_learning_velocity(metrics, learning_rate)

        # 11. Innovation: artifacts produced + decisions made
        score.innovation = self._compute_innovation(metrics)

        # Component health breakdown
        score.component_health = self._compute_component_health(metrics, score)

        _log.info(
            "Enterprise health: %.2f (%s) — op=%.2f mission=%.2f agents=%.2f providers=%.2f",
            score.overall_score,
            score.grade,
            score.operational,
            score.mission,
            score.agent_efficiency,
            score.provider_efficiency,
        )
        return score

    def _compute_operational_health(self, m: OperationalMetrics) -> float:
        """Operational health: uptime + queue depth + throughput."""
        # Uptime score: >3600s = 1.0, 0s = 0.5
        uptime_score = min(1.0, 0.5 + m.uptime_s / 7200.0)
        # Queue depth: 0 = 1.0, 100+ = 0.3
        queue_score = max(0.3, 1.0 - m.queue_depth / 100.0)
        # Throughput: >100/s = 1.0, 0 = 0.5
        throughput_score = min(1.0, 0.5 + m.event_bus_throughput_per_s / 200.0)
        # CPU/memory: <80% = healthy
        cpu_score = max(0.3, 1.0 - m.cpu_usage_pct / 100.0)
        mem_score = max(0.3, 1.0 - m.memory_usage_mb / 8192.0)
        return (uptime_score + queue_score + throughput_score + cpu_score + mem_score) / 5.0

    def _compute_mission_health(self, m: OperationalMetrics) -> float:
        """Mission health: completion percentage."""
        if m.total_missions == 0:
            return 1.0  # no missions = healthy
        return min(1.0, m.avg_mission_completion_pct / 100.0)

    def _compute_agent_efficiency(self, m: OperationalMetrics) -> float:
        """Agent efficiency: reliability x activity ratio."""
        if m.total_agents == 0:
            return 1.0
        activity_ratio = m.active_agents / max(1, m.total_agents)
        return m.avg_agent_reliability * 0.7 + activity_ratio * 0.3

    def _compute_provider_efficiency(self, m: OperationalMetrics) -> float:
        """Provider efficiency: reliability."""
        return m.avg_provider_reliability if m.avg_provider_reliability > 0 else 1.0

    def _compute_workflow_quality(self, m: OperationalMetrics) -> float:
        """Workflow quality: WBS completion ratio."""
        if m.total_wbs_nodes == 0:
            return 1.0
        return m.completed_wbs_nodes / m.total_wbs_nodes

    def _compute_execution_success(
        self,
        m: OperationalMetrics,
        history: list[float] | None,
    ) -> float:
        """Execution success rate from history or inferred from WBS."""
        if history and len(history) > 0:
            # Average of recent success rates
            return min(1.0, sum(history) / len(history))
        # Infer from WBS completion
        if m.total_wbs_nodes == 0:
            return 1.0
        return m.completed_wbs_nodes / m.total_wbs_nodes

    def _compute_risk_level(self, m: OperationalMetrics) -> float:
        """Risk level: inverse of open risks (higher = lower risk)."""
        if m.open_risks == 0:
            return 1.0
        # 0 risks = 1.0, 10+ = 0.3
        return max(0.3, 1.0 - m.open_risks / 10.0)

    def _compute_reliability(self, m: OperationalMetrics) -> float:
        """Reliability: average of agent + provider reliability."""
        return (m.avg_agent_reliability + m.avg_provider_reliability) / 2.0

    def _compute_cost_efficiency(
        self,
        m: OperationalMetrics,
        cost_history: list[float] | None,
    ) -> float:
        """Cost efficiency: budget utilization (lower = better)."""
        if m.total_budget_usd == 0:
            return 1.0
        utilization = m.total_spent_usd / m.total_budget_usd
        # 0% = 1.0, 100% = 0.0, >100% = 0.0
        return max(0.0, 1.0 - utilization)

    def _compute_learning_velocity(
        self,
        m: OperationalMetrics,
        learning_rate: float,
    ) -> float:
        """Learning velocity: rate of experience accumulation."""
        if m.total_experiences == 0:
            return 0.5  # neutral — no learning yet
        # learning_rate is experiences per hour
        # 10+/hour = 1.0, 0 = 0.5
        return min(1.0, 0.5 + learning_rate / 20.0)

    def _compute_innovation(self, m: OperationalMetrics) -> float:
        """Innovation: artifacts + decisions (normalized)."""
        # 10+ artifacts = 1.0, 0 = 0.5
        artifact_score = min(1.0, 0.5 + m.total_artifacts / 20.0)
        # 10+ decisions = 1.0, 0 = 0.5
        decision_score = min(1.0, 0.5 + m.total_decisions / 20.0)
        return (artifact_score + decision_score) / 2.0

    def _compute_component_health(
        self,
        m: OperationalMetrics,
        score: EnterpriseHealthScore,
    ) -> list[ComponentHealth]:
        """Break down health by component."""
        components: list[ComponentHealth] = []

        components.append(
            ComponentHealth(
                component="kernel",
                score=score.operational,
                status="healthy" if score.operational >= 0.8 else "degraded",
                metrics={"uptime_s": m.uptime_s, "event_throughput": m.event_bus_throughput_per_s},
            )
        )
        components.append(
            ComponentHealth(
                component="mission_manager",
                score=score.mission,
                status="healthy" if score.mission >= 0.8 else "degraded",
                metrics={"total_missions": m.total_missions, "active": m.active_missions},
            )
        )
        components.append(
            ComponentHealth(
                component="agent_registry",
                score=score.agent_efficiency,
                status="healthy" if score.agent_efficiency >= 0.7 else "degraded",
                metrics={"total_agents": m.total_agents, "active": m.active_agents},
            )
        )
        components.append(
            ComponentHealth(
                component="model_router",
                score=score.provider_efficiency,
                status="healthy" if score.provider_efficiency >= 0.7 else "degraded",
                metrics={"avg_reliability": m.avg_provider_reliability},
            )
        )
        components.append(
            ComponentHealth(
                component="memory",
                score=1.0 - (m.memory_usage_mb / 8192.0),
                status="healthy" if m.memory_usage_mb < 6144 else "degraded",
                metrics={"usage_mb": m.memory_usage_mb},
            )
        )
        components.append(
            ComponentHealth(
                component="budget",
                score=score.cost_efficiency,
                status="healthy" if score.cost_efficiency >= 0.5 else "degraded",
                metrics={
                    "budget_usd": m.total_budget_usd,
                    "spent_usd": m.total_spent_usd,
                    "utilization_pct": (m.total_spent_usd / m.total_budget_usd * 100)
                    if m.total_budget_usd > 0
                    else 0,
                },
            )
        )
        return components
