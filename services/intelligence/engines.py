"""Predictive Analytics + Optimization + Risk engines.

PredictiveAnalyticsEngine: forecasts failures, bottlenecks, outages, etc.
OptimizationEngine: generates recommendations (never auto-applies).
RiskAnalysisEngine: detects risks + computes risk heat map.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from core.logging import get_logger
from services.intelligence.models import (
    CapacityForecast,
    CostBreakdown,
    CostForecast,
    ForecastConfidence,
    ForecastResult,
    ForecastType,
    OperationalMetrics,
    OptimizationRecommendation,
    OptimizationType,
    RiskAssessment,
    RiskLevel,
    RiskType,
)

_log = get_logger(__name__)

__all__ = [
    "OptimizationEngine",
    "PredictiveAnalyticsEngine",
    "RiskAnalysisEngine",
]


class PredictiveAnalyticsEngine:
    """Forecasts future system states based on current metrics + trends.

    All forecasts are probabilistic (0.0-1.0) with a confidence level
    and recommended actions. Forecasts are never auto-acted upon.
    """

    def forecast_all(
        self,
        metrics: OperationalMetrics,
        *,
        spend_rate_per_day: float = 0.0,
        success_rate_trend: list[float] | None = None,
    ) -> list[ForecastResult]:
        """Generate all applicable forecasts."""
        forecasts: list[ForecastResult] = []
        forecasts.append(self.forecast_mission_failure(metrics, success_rate_trend))
        forecasts.append(self.forecast_workflow_bottleneck(metrics))
        forecasts.append(self.forecast_provider_outage(metrics))
        forecasts.append(self.forecast_agent_degradation(metrics))
        forecasts.append(self.forecast_memory_saturation(metrics))
        forecasts.append(self.forecast_queue_congestion(metrics))
        forecasts.append(self.forecast_budget_overrun(metrics, spend_rate_per_day))
        forecasts.append(self.forecast_deadline_risk(metrics))
        forecasts.append(self.forecast_resource_exhaustion(metrics))
        forecasts.append(self.forecast_capacity_limit(metrics))
        # Filter out low-probability forecasts
        return [f for f in forecasts if f.probability > 0.05]

    def forecast_mission_failure(
        self,
        metrics: OperationalMetrics,
        trend: list[float] | None,
    ) -> ForecastResult:
        """Predict mission failure probability."""
        prob = 0.1  # base rate
        evidence: dict[str, Any] = {}
        if trend and len(trend) >= 3:
            recent = trend[-3:]
            avg = sum(recent) / len(recent)
            failure_rate = 1.0 - avg
            prob = max(prob, failure_rate)
            evidence["recent_success_rates"] = recent
            evidence["failure_rate"] = round(failure_rate, 4)
        if metrics.open_risks > 3:
            prob += 0.15
            evidence["open_risks"] = metrics.open_risks
        if metrics.queue_depth > 50:
            prob += 0.10
            evidence["queue_depth"] = metrics.queue_depth
        prob = min(0.95, prob)
        confidence = (
            ForecastConfidence.HIGH.value if prob > 0.5 else ForecastConfidence.MEDIUM.value
        )
        return ForecastResult(
            forecast_type=ForecastType.MISSION_FAILURE.value,
            target="active_missions",
            prediction=f"{prob:.0%} probability of mission failure in next 24h",
            probability=prob,
            confidence=confidence,
            time_horizon="24h",
            evidence=evidence,
            recommended_actions=[
                "Review open risks and mitigate critical ones",
                "Reduce queue depth by pausing low-priority missions",
                "Increase concurrency limits if resources allow",
            ]
            if prob > 0.3
            else ["No action needed — probability is low"],
        )

    def forecast_workflow_bottleneck(
        self,
        metrics: OperationalMetrics,
    ) -> ForecastResult:
        """Predict workflow bottlenecks."""
        prob = 0.1
        evidence: dict[str, Any] = {}
        if metrics.queue_depth > 30:
            prob = 0.4 + (metrics.queue_depth - 30) / 100.0
            evidence["queue_depth"] = metrics.queue_depth
        if metrics.active_missions > 10 and metrics.active_agents < 5:
            prob += 0.15
            evidence["mission_to_agent_ratio"] = metrics.active_missions / max(
                1, metrics.active_agents
            )
        prob = min(0.9, prob)
        return ForecastResult(
            forecast_type=ForecastType.WORKFLOW_BOTTLENECK.value,
            target="task_queue",
            prediction=f"{prob:.0%} probability of workflow bottleneck in next 6h",
            probability=prob,
            confidence=ForecastConfidence.MEDIUM.value,
            time_horizon="6h",
            evidence=evidence,
            recommended_actions=[
                "Scale up agent pool",
                "Prioritize critical mission tasks",
                "Consider parallelizing independent WBS nodes",
            ]
            if prob > 0.3
            else ["Monitor queue depth"],
        )

    def forecast_provider_outage(
        self,
        metrics: OperationalMetrics,
    ) -> ForecastResult:
        """Predict provider outages from reliability degradation."""
        prob = 0.05
        evidence: dict[str, Any] = {}
        if metrics.avg_provider_reliability < 0.8:
            prob = 0.2 + (1.0 - metrics.avg_provider_reliability) * 0.5
            evidence["avg_provider_reliability"] = metrics.avg_provider_reliability
        prob = min(0.85, prob)
        return ForecastResult(
            forecast_type=ForecastType.PROVIDER_OUTAGE.value,
            target="model_router",
            prediction=f"{prob:.0%} probability of provider outage in next 24h",
            probability=prob,
            confidence=ForecastConfidence.LOW.value
            if prob < 0.2
            else ForecastConfidence.MEDIUM.value,
            time_horizon="24h",
            evidence=evidence,
            recommended_actions=[
                "Configure failover providers",
                "Pre-warm backup provider connections",
                "Review provider rate limits",
            ]
            if prob > 0.2
            else ["Monitor provider reliability"],
        )

    def forecast_agent_degradation(
        self,
        metrics: OperationalMetrics,
    ) -> ForecastResult:
        """Predict agent degradation."""
        prob = 0.05
        evidence: dict[str, Any] = {}
        if metrics.avg_agent_reliability < 0.8:
            prob = 0.15 + (1.0 - metrics.avg_agent_reliability) * 0.4
            evidence["avg_agent_reliability"] = metrics.avg_agent_reliability
        prob = min(0.8, prob)
        return ForecastResult(
            forecast_type=ForecastType.AGENT_DEGRADATION.value,
            target="agent_registry",
            prediction=f"{prob:.0%} probability of agent degradation in next 12h",
            probability=prob,
            confidence=ForecastConfidence.MEDIUM.value,
            time_horizon="12h",
            evidence=evidence,
            recommended_actions=[
                "Review agent health checks",
                "Consider restarting degraded agents",
                "Switch to backup agents for critical tasks",
            ]
            if prob > 0.2
            else ["Monitor agent reliability"],
        )

    def forecast_memory_saturation(
        self,
        metrics: OperationalMetrics,
    ) -> ForecastResult:
        """Predict memory saturation."""
        prob = 0.05
        evidence: dict[str, Any] = {}
        if metrics.memory_usage_mb > 6144:  # >75% of 8GB
            prob = 0.3 + (metrics.memory_usage_mb - 6144) / 8192.0
            evidence["memory_usage_mb"] = metrics.memory_usage_mb
        prob = min(0.9, prob)
        return ForecastResult(
            forecast_type=ForecastType.MEMORY_SATURATION.value,
            target="system_memory",
            prediction=f"{prob:.0%} probability of memory saturation in next 6h",
            probability=prob,
            confidence=ForecastConfidence.HIGH.value
            if prob > 0.4
            else ForecastConfidence.MEDIUM.value,
            time_horizon="6h",
            evidence=evidence,
            recommended_actions=[
                "Increase memory limits",
                "Run garbage collection",
                "Close unused agent processes",
            ]
            if prob > 0.3
            else ["Monitor memory usage"],
        )

    def forecast_queue_congestion(
        self,
        metrics: OperationalMetrics,
    ) -> ForecastResult:
        """Predict queue congestion."""
        prob = 0.1
        evidence: dict[str, Any] = {}
        if metrics.queue_depth > 20:
            prob = min(0.85, 0.2 + metrics.queue_depth / 100.0)
            evidence["queue_depth"] = metrics.queue_depth
        return ForecastResult(
            forecast_type=ForecastType.QUEUE_CONGESTION.value,
            target="task_queue",
            prediction=f"{prob:.0%} probability of queue congestion in next 3h",
            probability=prob,
            confidence=ForecastConfidence.HIGH.value,
            time_horizon="3h",
            evidence=evidence,
            recommended_actions=[
                "Increase max_concurrent_tasks",
                "Pause low-priority missions",
                "Scale horizontally",
            ]
            if prob > 0.3
            else ["Monitor queue depth"],
        )

    def forecast_budget_overrun(
        self,
        metrics: OperationalMetrics,
        spend_rate_per_day: float,
    ) -> ForecastResult:
        """Predict budget overruns."""
        prob = 0.1
        evidence: dict[str, Any] = {}
        if metrics.total_budget_usd > 0:
            utilization = metrics.total_spent_usd / metrics.total_budget_usd
            if utilization > 0.7:
                prob = 0.3 + (utilization - 0.7) * 2.0
                evidence["budget_utilization"] = round(utilization, 4)
            if spend_rate_per_day > 0:
                remaining = metrics.total_budget_usd - metrics.total_spent_usd
                days_left = remaining / spend_rate_per_day if spend_rate_per_day > 0 else 999
                if days_left < 7:
                    prob = max(prob, 0.7)
                    evidence["days_until_exhausted"] = round(days_left, 1)
        prob = min(0.95, prob)
        return ForecastResult(
            forecast_type=ForecastType.BUDGET_OVERRUN.value,
            target="budget",
            prediction=f"{prob:.0%} probability of budget overrun",
            probability=prob,
            confidence=ForecastConfidence.HIGH.value
            if prob > 0.5
            else ForecastConfidence.MEDIUM.value,
            time_horizon="7d",
            evidence=evidence,
            recommended_actions=[
                "Reduce spend rate by switching to cheaper providers",
                "Pause non-critical missions",
                "Request budget increase",
            ]
            if prob > 0.3
            else ["Monitor budget utilization"],
        )

    def forecast_deadline_risk(
        self,
        metrics: OperationalMetrics,
    ) -> ForecastResult:
        """Predict deadline risk for active missions."""
        prob = 0.15
        evidence: dict[str, Any] = {}
        if metrics.avg_mission_completion_pct < 50 and metrics.active_missions > 0:
            prob = 0.35
            evidence["avg_completion_pct"] = metrics.avg_mission_completion_pct
        if metrics.queue_depth > 30:
            prob += 0.15
            evidence["queue_depth"] = metrics.queue_depth
        prob = min(0.85, prob)
        return ForecastResult(
            forecast_type=ForecastType.DEADLINE_RISK.value,
            target="active_missions",
            prediction=f"{prob:.0%} probability of deadline miss for active missions",
            probability=prob,
            confidence=ForecastConfidence.MEDIUM.value,
            time_horizon="24h",
            evidence=evidence,
            recommended_actions=[
                "Replan missions to prioritize critical deliverables",
                "Allocate additional agents to behind-schedule missions",
                "Request deadline extensions if needed",
            ]
            if prob > 0.3
            else ["Monitor mission progress"],
        )

    def forecast_resource_exhaustion(
        self,
        metrics: OperationalMetrics,
    ) -> ForecastResult:
        """Predict resource exhaustion."""
        prob = 0.05
        evidence: dict[str, Any] = {}
        if metrics.cpu_usage_pct > 80:
            prob = 0.3 + (metrics.cpu_usage_pct - 80) / 50.0
            evidence["cpu_usage_pct"] = metrics.cpu_usage_pct
        if metrics.memory_usage_mb > 7000:
            prob = max(prob, 0.4)
            evidence["memory_usage_mb"] = metrics.memory_usage_mb
        prob = min(0.9, prob)
        return ForecastResult(
            forecast_type=ForecastType.RESOURCE_EXHAUSTION.value,
            target="system_resources",
            prediction=f"{prob:.0%} probability of resource exhaustion in next 12h",
            probability=prob,
            confidence=ForecastConfidence.HIGH.value
            if prob > 0.4
            else ForecastConfidence.MEDIUM.value,
            time_horizon="12h",
            evidence=evidence,
            recommended_actions=[
                "Scale up CPU/memory limits",
                "Reduce concurrent task limits",
                "Offload work to distributed nodes",
            ]
            if prob > 0.3
            else ["Monitor resource usage"],
        )

    def forecast_capacity_limit(
        self,
        metrics: OperationalMetrics,
    ) -> ForecastResult:
        """Predict capacity limit approaching."""
        prob = 0.1
        evidence: dict[str, Any] = {}
        if metrics.active_agents > 0 and metrics.total_agents > 0:
            agent_util = metrics.active_agents / metrics.total_agents
            if agent_util > 0.8:
                prob = 0.3 + (agent_util - 0.8) * 2.0
                evidence["agent_utilization"] = round(agent_util, 4)
        prob = min(0.85, prob)
        return ForecastResult(
            forecast_type=ForecastType.CAPACITY_LIMIT.value,
            target="agent_pool",
            prediction=f"{prob:.0%} probability of hitting capacity limits in next 24h",
            probability=prob,
            confidence=ForecastConfidence.MEDIUM.value,
            time_horizon="24h",
            evidence=evidence,
            recommended_actions=[
                "Register additional agents",
                "Scale horizontally across nodes",
                "Increase max_concurrent_agents limit",
            ]
            if prob > 0.3
            else ["Monitor agent utilization"],
        )


class OptimizationEngine:
    """Generates optimization recommendations.

    Recommendations are NEVER auto-applied. They are presented to the
    operator for review. Each recommendation includes current state,
    recommended state, expected improvement, and confidence.
    """

    def generate_all(
        self,
        metrics: OperationalMetrics,
        *,
        agent_reliability_scores: dict[str, float] | None = None,
        provider_reliability_scores: dict[str, float] | None = None,
    ) -> list[OptimizationRecommendation]:
        """Generate all applicable optimization recommendations."""
        recs: list[OptimizationRecommendation] = []
        recs.extend(self.recommend_routing(metrics, agent_reliability_scores))
        recs.extend(self.recommend_provider_selection(metrics, provider_reliability_scores))
        recs.extend(self.recommend_agent_assignment(metrics, agent_reliability_scores))
        recs.extend(self.recommend_concurrency(metrics))
        recs.extend(self.recommend_retry_strategy(metrics))
        recs.extend(self.recommend_caching(metrics))
        recs.extend(self.recommend_memory_utilization(metrics))
        recs.extend(self.recommend_scheduling(metrics))
        return [r for r in recs if r.estimated_impact > 0.1]

    def recommend_routing(
        self,
        metrics: OperationalMetrics,
        agent_scores: dict[str, float] | None,
    ) -> list[OptimizationRecommendation]:
        """Recommend routing optimizations."""
        recs: list[OptimizationRecommendation] = []
        if agent_scores and len(agent_scores) > 1:
            scores = list(agent_scores.values())
            spread = max(scores) - min(scores)
            if spread > 0.2:
                best_agent = max(agent_scores, key=lambda k: agent_scores[k])
                worst_agent = min(agent_scores, key=lambda k: agent_scores[k])
                recs.append(
                    OptimizationRecommendation(
                        optimization_type=OptimizationType.ROUTING.value,
                        title=f"Route more traffic to '{best_agent}' and less to '{worst_agent}'",
                        description=f"Agent reliability spread is {spread:.2f}. "
                        f"Routing to higher-reliability agents improves success rate.",
                        current_state=f"'{worst_agent}' reliability: {agent_scores[worst_agent]:.2f}",
                        recommended_state=f"Shift 30% of traffic from '{worst_agent}' to '{best_agent}'",
                        expected_improvement=f"+{spread * 0.15:.0%} success rate",
                        estimated_impact=min(0.8, spread),
                        confidence=0.8,
                        priority="high" if spread > 0.3 else "normal",
                        affected_components=[worst_agent, best_agent],
                        evidence={"reliability_spread": round(spread, 4)},
                    )
                )
        return recs

    def recommend_provider_selection(
        self,
        metrics: OperationalMetrics,
        provider_scores: dict[str, float] | None,
    ) -> list[OptimizationRecommendation]:
        """Recommend provider selection optimizations."""
        recs: list[OptimizationRecommendation] = []
        if metrics.avg_provider_reliability < 0.85 and provider_scores:
            best = max(provider_scores, key=lambda k: provider_scores[k])
            recs.append(
                OptimizationRecommendation(
                    optimization_type=OptimizationType.PROVIDER_SELECTION.value,
                    title=f"Prioritize provider '{best}' for critical tasks",
                    description=f"Average provider reliability is {metrics.avg_provider_reliability:.2f}. "
                    f"Provider '{best}' has the highest reliability.",
                    current_state=f"Avg provider reliability: {metrics.avg_provider_reliability:.2f}",
                    recommended_state=f"Set '{best}' as priority 1 for critical tasks",
                    expected_improvement=f"+{(provider_scores[best] - metrics.avg_provider_reliability) * 0.5:.0%} reliability",
                    estimated_impact=0.6,
                    confidence=0.75,
                    priority="high",
                    affected_components=["model_router", best],
                    evidence={"best_provider_reliability": provider_scores[best]},
                )
            )
        return recs

    def recommend_agent_assignment(
        self,
        metrics: OperationalMetrics,
        agent_scores: dict[str, float] | None,
    ) -> list[OptimizationRecommendation]:
        """Recommend agent assignment optimizations."""
        recs: list[OptimizationRecommendation] = []
        if metrics.total_agents > 0 and metrics.active_agents / metrics.total_agents > 0.85:
            recs.append(
                OptimizationRecommendation(
                    optimization_type=OptimizationType.AGENT_ASSIGNMENT.value,
                    title="Register additional agents to reduce load",
                    description=f"Agent utilization is {metrics.active_agents / metrics.total_agents:.0%}. "
                    "High utilization may cause delays.",
                    current_state=f"{metrics.active_agents}/{metrics.total_agents} agents active",
                    recommended_state="Register 2-3 additional agents",
                    expected_improvement="-20% avg task latency",
                    estimated_impact=0.5,
                    confidence=0.7,
                    priority="normal",
                    affected_components=["agent_registry"],
                )
            )
        return recs

    def recommend_concurrency(
        self,
        metrics: OperationalMetrics,
    ) -> list[OptimizationRecommendation]:
        """Recommend concurrency adjustments."""
        recs: list[OptimizationRecommendation] = []
        if metrics.queue_depth > 20 and metrics.cpu_usage_pct < 70:
            recs.append(
                OptimizationRecommendation(
                    optimization_type=OptimizationType.CONCURRENCY.value,
                    title="Increase max_concurrent_tasks",
                    description=f"Queue depth is {metrics.queue_depth} but CPU usage is only "
                    f"{metrics.cpu_usage_pct:.0f}%. Increasing concurrency will drain the queue faster.",
                    current_state=f"queue_depth={metrics.queue_depth}, cpu={metrics.cpu_usage_pct:.0f}%",
                    recommended_state="Increase max_concurrent_tasks by 50%",
                    expected_improvement=f"-{metrics.queue_depth * 0.5:.0f} queue depth",
                    estimated_impact=0.7,
                    confidence=0.85,
                    priority="high",
                    affected_components=["task_queue", "resource_manager"],
                )
            )
        return recs

    def recommend_retry_strategy(
        self,
        metrics: OperationalMetrics,
    ) -> list[OptimizationRecommendation]:
        """Recommend retry strategy adjustments."""
        recs: list[OptimizationRecommendation] = []
        if metrics.avg_provider_reliability < 0.8:
            recs.append(
                OptimizationRecommendation(
                    optimization_type=OptimizationType.RETRY_STRATEGY.value,
                    title="Increase retry count for unreliable providers",
                    description=f"Provider reliability is {metrics.avg_provider_reliability:.2f}. "
                    "More retries with exponential backoff will improve success rate.",
                    current_state="max_retries=2",
                    recommended_state="max_retries=3 with exponential backoff",
                    expected_improvement="+10% success rate",
                    estimated_impact=0.4,
                    confidence=0.7,
                    priority="normal",
                    affected_components=["model_router"],
                )
            )
        return recs

    def recommend_caching(
        self,
        metrics: OperationalMetrics,
    ) -> list[OptimizationRecommendation]:
        """Recommend caching optimizations."""
        recs: list[OptimizationRecommendation] = []
        if metrics.total_experiences > 100:
            recs.append(
                OptimizationRecommendation(
                    optimization_type=OptimizationType.CACHING.value,
                    title="Enable prompt caching for repeated patterns",
                    description=f"{metrics.total_experiences} experiences recorded. "
                    "Common patterns can be cached to reduce LLM calls.",
                    current_state="No prompt caching",
                    recommended_state="Enable prompt caching for top 10 patterns",
                    expected_improvement="-15% LLM cost",
                    estimated_impact=0.5,
                    confidence=0.75,
                    priority="normal",
                    affected_components=["model_router", "prompt_registry"],
                )
            )
        return recs

    def recommend_memory_utilization(
        self,
        metrics: OperationalMetrics,
    ) -> list[OptimizationRecommendation]:
        """Recommend memory utilization optimizations."""
        recs: list[OptimizationRecommendation] = []
        if metrics.memory_usage_mb > 5120:
            recs.append(
                OptimizationRecommendation(
                    optimization_type=OptimizationType.MEMORY_UTILIZATION.value,
                    title="Run memory compression on experience store",
                    description=f"Memory usage is {metrics.memory_usage_mb:.0f}MB. "
                    "Compressing similar experiences reduces memory footprint.",
                    current_state=f"{metrics.memory_usage_mb:.0f}MB used",
                    recommended_state="Run experience compressor",
                    expected_improvement="-20% memory usage",
                    estimated_impact=0.4,
                    confidence=0.8,
                    priority="normal",
                    affected_components=["experience_store", "memory_manager"],
                )
            )
        return recs

    def recommend_scheduling(
        self,
        metrics: OperationalMetrics,
    ) -> list[OptimizationRecommendation]:
        """Recommend scheduling optimizations."""
        recs: list[OptimizationRecommendation] = []
        if metrics.pending_approvals > 5:
            recs.append(
                OptimizationRecommendation(
                    optimization_type=OptimizationType.SCHEDULING.value,
                    title="Batch approval notifications",
                    description=f"{metrics.pending_approvals} approvals pending. "
                    "Batching notifications reduces context switching.",
                    current_state=f"{metrics.pending_approvals} pending approvals",
                    recommended_state="Send daily approval digest instead of per-request",
                    expected_improvement="-50% approval latency",
                    estimated_impact=0.3,
                    confidence=0.6,
                    priority="low",
                    affected_components=["approval_gates"],
                )
            )
        return recs


class RiskAnalysisEngine:
    """Detects risks and computes a risk heat map.

    Risks are detected from current metrics + forecasts. Each risk has
    a probability, impact, and risk_score (probability x impact).
    """

    def assess_all(
        self,
        metrics: OperationalMetrics,
        forecasts: list[ForecastResult] | None = None,
    ) -> list[RiskAssessment]:
        """Detect all current risks."""
        risks: list[RiskAssessment] = []
        risks.append(self.assess_budget_risk(metrics))
        risks.append(self.assess_deadline_risk(metrics))
        risks.append(self.assess_capacity_risk(metrics))
        risks.append(self.assess_reliability_risk(metrics))
        risks.append(self.assess_quality_risk(metrics))
        risks.append(self.assess_operational_risk(metrics))
        # Also convert high-probability forecasts to risks
        if forecasts:
            for f in forecasts:
                if f.probability > 0.5:
                    risks.append(
                        RiskAssessment(
                            risk_type=RiskType.OPERATIONAL.value,
                            level=self._prob_to_level(f.probability),
                            description=f.forecast_type.replace("_", " ").title()
                            + ": "
                            + f.prediction,
                            probability=f.probability,
                            impact=0.6,
                            risk_score=f.probability * 0.6,
                            affected_components=[f.target],
                            mitigation="; ".join(f.recommended_actions[:2]),
                            evidence={"forecast_id": f.forecast_id},
                        )
                    )
        return [r for r in risks if r.risk_score > 0.05]

    def _prob_to_level(self, prob: float) -> str:
        if prob >= 0.7:
            return RiskLevel.CRITICAL.value
        if prob >= 0.5:
            return RiskLevel.HIGH.value
        if prob >= 0.3:
            return RiskLevel.MEDIUM.value
        return RiskLevel.LOW.value

    def assess_budget_risk(self, metrics: OperationalMetrics) -> RiskAssessment:
        """Assess budget overrun risk."""
        prob = 0.1
        if metrics.total_budget_usd > 0:
            util = metrics.total_spent_usd / metrics.total_budget_usd
            if util > 0.8:
                prob = 0.7
            elif util > 0.6:
                prob = 0.4
        impact = 0.8
        return RiskAssessment(
            risk_type=RiskType.BUDGET.value,
            level=self._prob_to_level(prob),
            description=f"Budget utilization at {metrics.total_spent_usd / max(1, metrics.total_budget_usd) * 100:.0f}%",
            probability=prob,
            impact=impact,
            risk_score=prob * impact,
            affected_components=["budget"],
            mitigation="Reduce spend rate or request budget increase",
        )

    def assess_deadline_risk(self, metrics: OperationalMetrics) -> RiskAssessment:
        """Assess deadline miss risk."""
        prob = 0.15
        if metrics.avg_mission_completion_pct < 50 and metrics.active_missions > 0:
            prob = 0.4
        impact = 0.7
        return RiskAssessment(
            risk_type=RiskType.DEADLINE.value,
            level=self._prob_to_level(prob),
            description=f"Average mission completion: {metrics.avg_mission_completion_pct:.0f}%",
            probability=prob,
            impact=impact,
            risk_score=prob * impact,
            affected_components=["missions"],
            mitigation="Replan missions or allocate more agents",
        )

    def assess_capacity_risk(self, metrics: OperationalMetrics) -> RiskAssessment:
        """Assess capacity exhaustion risk."""
        prob = 0.1
        if metrics.total_agents > 0:
            util = metrics.active_agents / metrics.total_agents
            if util > 0.85:
                prob = 0.4
        impact = 0.6
        return RiskAssessment(
            risk_type=RiskType.CAPACITY.value,
            level=self._prob_to_level(prob),
            description=f"Agent utilization: {metrics.active_agents / max(1, metrics.total_agents) * 100:.0f}%",
            probability=prob,
            impact=impact,
            risk_score=prob * impact,
            affected_components=["agent_registry"],
            mitigation="Register additional agents or scale horizontally",
        )

    def assess_reliability_risk(self, metrics: OperationalMetrics) -> RiskAssessment:
        """Assess reliability degradation risk."""
        prob = 0.1
        if metrics.avg_agent_reliability < 0.8 or metrics.avg_provider_reliability < 0.8:
            prob = 0.35
        impact = 0.7
        return RiskAssessment(
            risk_type=RiskType.RELIABILITY.value,
            level=self._prob_to_level(prob),
            description=f"Agent reliability: {metrics.avg_agent_reliability:.2f}, Provider reliability: {metrics.avg_provider_reliability:.2f}",
            probability=prob,
            impact=impact,
            risk_score=prob * impact,
            affected_components=["agent_registry", "model_router"],
            mitigation="Switch to more reliable agents/providers",
        )

    def assess_quality_risk(self, metrics: OperationalMetrics) -> RiskAssessment:
        """Assess quality degradation risk."""
        prob = 0.1
        if metrics.total_wbs_nodes > 0:
            completion = metrics.completed_wbs_nodes / metrics.total_wbs_nodes
            if completion < 0.7 and metrics.active_missions > 0:
                prob = 0.3
        impact = 0.5
        return RiskAssessment(
            risk_type=RiskType.QUALITY.value,
            level=self._prob_to_level(prob),
            description=f"WBS completion rate: {metrics.completed_wbs_nodes / max(1, metrics.total_wbs_nodes) * 100:.0f}%",
            probability=prob,
            impact=impact,
            risk_score=prob * impact,
            affected_components=["missions"],
            mitigation="Review failed WBS nodes and apply lessons learned",
        )

    def assess_operational_risk(self, metrics: OperationalMetrics) -> RiskAssessment:
        """Assess general operational risk."""
        prob = 0.1
        if metrics.queue_depth > 50:
            prob = 0.3
        if metrics.open_risks > 5:
            prob += 0.15
        prob = min(0.8, prob)
        impact = 0.5
        return RiskAssessment(
            risk_type=RiskType.OPERATIONAL.value,
            level=self._prob_to_level(prob),
            description=f"Queue depth: {metrics.queue_depth}, Open risks: {metrics.open_risks}",
            probability=prob,
            impact=impact,
            risk_score=prob * impact,
            affected_components=["task_queue", "risk_register"],
            mitigation="Reduce queue depth and mitigate open risks",
        )

    def heat_map(self, risks: list[RiskAssessment]) -> dict[str, Any]:
        """Generate a risk heat map (probability vs impact grid)."""
        grid: dict[str, list[str]] = {
            "negligible": [],
            "low": [],
            "medium": [],
            "high": [],
            "critical": [],
        }
        for risk in risks:
            grid[risk.level].append(risk.risk_type)
        return {
            "by_level": {k: len(v) for k, v in grid.items()},
            "details": {k: v for k, v in grid.items() if v},
            "total_risks": len(risks),
            "highest_risk_score": max((r.risk_score for r in risks), default=0.0),
        }


class CapacityPlanningEngine:
    """Capacity planning — projects resource usage into the future."""

    def forecast_capacity(
        self,
        metrics: OperationalMetrics,
        *,
        growth_rate_per_day: float = 0.02,
    ) -> list[CapacityForecast]:
        """Forecast capacity for all resource types."""
        forecasts: list[CapacityForecast] = []
        # Agents
        forecasts.append(
            CapacityForecast(
                resource="agents",
                current_usage=float(metrics.active_agents),
                current_capacity=float(metrics.total_agents),
                utilization_pct=(metrics.active_agents / max(1, metrics.total_agents) * 100)
                if metrics.total_agents > 0
                else 0,
                projected_usage_7d=metrics.active_agents * (1 + growth_rate_per_day * 7),
                projected_usage_30d=metrics.active_agents * (1 + growth_rate_per_day * 30),
                exhaustion_eta=self._exhaustion_eta(
                    metrics.active_agents, metrics.total_agents, growth_rate_per_day
                ),
                recommendation="Register additional agents"
                if metrics.active_agents / max(1, metrics.total_agents) > 0.8
                else "Sufficient capacity",
            )
        )
        # Budget
        forecasts.append(
            CapacityForecast(
                resource="budget",
                current_usage=metrics.total_spent_usd,
                current_capacity=metrics.total_budget_usd,
                utilization_pct=(metrics.total_spent_usd / max(1, metrics.total_budget_usd) * 100)
                if metrics.total_budget_usd > 0
                else 0,
                projected_usage_7d=metrics.total_spent_usd * (1 + growth_rate_per_day * 7),
                projected_usage_30d=metrics.total_spent_usd * (1 + growth_rate_per_day * 30),
                exhaustion_eta=self._exhaustion_eta(
                    metrics.total_spent_usd, metrics.total_budget_usd, growth_rate_per_day
                ),
                recommendation="Request budget increase"
                if metrics.total_spent_usd / max(1, metrics.total_budget_usd) > 0.7
                else "Sufficient budget",
            )
        )
        # Memory
        forecasts.append(
            CapacityForecast(
                resource="memory",
                current_usage=metrics.memory_usage_mb,
                current_capacity=8192.0,
                utilization_pct=metrics.memory_usage_mb / 8192.0 * 100,
                projected_usage_7d=metrics.memory_usage_mb * (1 + growth_rate_per_day * 7),
                projected_usage_30d=metrics.memory_usage_mb * (1 + growth_rate_per_day * 30),
                exhaustion_eta=self._exhaustion_eta(
                    metrics.memory_usage_mb, 8192.0, growth_rate_per_day
                ),
                recommendation="Increase memory limit"
                if metrics.memory_usage_mb > 6144
                else "Sufficient memory",
            )
        )
        # CPU
        forecasts.append(
            CapacityForecast(
                resource="cpu",
                current_usage=metrics.cpu_usage_pct,
                current_capacity=100.0,
                utilization_pct=metrics.cpu_usage_pct,
                projected_usage_7d=min(100, metrics.cpu_usage_pct * (1 + growth_rate_per_day * 7)),
                projected_usage_30d=min(
                    100, metrics.cpu_usage_pct * (1 + growth_rate_per_day * 30)
                ),
                exhaustion_eta=self._exhaustion_eta(
                    metrics.cpu_usage_pct, 100.0, growth_rate_per_day
                ),
                recommendation="Scale up CPU" if metrics.cpu_usage_pct > 80 else "Sufficient CPU",
            )
        )
        return forecasts

    def _exhaustion_eta(
        self,
        current: float,
        capacity: float,
        growth_rate: float,
    ) -> str | None:
        """Calculate when capacity will be exhausted."""
        if current >= capacity or growth_rate <= 0:
            return None
        remaining = capacity - current
        daily_growth = current * growth_rate
        if daily_growth <= 0:
            return None
        days_left = remaining / daily_growth
        if days_left > 365:
            return None
        eta = datetime.now(UTC) + timedelta(days=days_left)
        return eta.isoformat()


class CostIntelligenceEngine:
    """Cost analysis + forecasting."""

    def analyze(
        self,
        metrics: OperationalMetrics,
        *,
        by_provider: dict[str, float] | None = None,
        by_agent: dict[str, float] | None = None,
        by_capability: dict[str, float] | None = None,
        by_mission: dict[str, float] | None = None,
        cost_trend: list[dict[str, Any]] | None = None,
    ) -> CostBreakdown:
        """Analyze costs across dimensions."""
        total_tasks = max(1, metrics.total_wbs_nodes)
        total_missions = max(1, metrics.total_missions)
        utilization = (
            (metrics.total_spent_usd / metrics.total_budget_usd * 100)
            if metrics.total_budget_usd > 0
            else 0
        )
        # Cost efficiency: lower utilization + more artifacts = more efficient
        efficiency = max(0.0, 1.0 - utilization / 100.0) * 0.7
        if metrics.total_artifacts > 0:
            efficiency += min(0.3, metrics.total_artifacts / (metrics.total_spent_usd + 1) * 100)
        return CostBreakdown(
            total_spent_usd=metrics.total_spent_usd,
            total_budget_usd=metrics.total_budget_usd,
            by_provider=by_provider or {},
            by_agent=by_agent or {},
            by_capability=by_capability or {},
            by_mission=by_mission or {},
            avg_cost_per_task=metrics.total_spent_usd / total_tasks,
            avg_cost_per_mission=metrics.total_spent_usd / total_missions,
            cost_trend=cost_trend or [],
            projected_monthly_spend=metrics.total_spent_usd * 30,  # rough projection
            budget_utilization_pct=utilization,
            cost_efficiency_score=min(1.0, efficiency),
        )

    def forecast(
        self,
        metrics: OperationalMetrics,
        *,
        spend_rate_per_day: float = 0.0,
    ) -> CostForecast:
        """Forecast future costs."""
        daily = spend_rate_per_day or (metrics.total_spent_usd / max(1, metrics.uptime_s / 86400))
        weekly = daily * 7
        monthly = daily * 30
        overrun_prob = 0.1
        days_left: int | None = None
        if metrics.total_budget_usd > 0 and daily > 0:
            remaining = metrics.total_budget_usd - metrics.total_spent_usd
            days_left = int(remaining / daily) if daily > 0 else None
            if days_left is not None and days_left < 30:
                overrun_prob = 0.7
            elif days_left is not None and days_left < 60:
                overrun_prob = 0.3
        return CostForecast(
            projected_daily_spend_usd=daily,
            projected_weekly_spend_usd=weekly,
            projected_monthly_spend_usd=monthly,
            budget_overrun_probability=min(0.95, overrun_prob),
            days_until_budget_exhausted=days_left,
            recommended_budget_adjustment=monthly * 1.2 if overrun_prob > 0.5 else 0.0,
            confidence=ForecastConfidence.HIGH.value if daily > 0 else ForecastConfidence.LOW.value,
        )
