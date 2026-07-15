"""IntelligenceManager — top-level facade for the Enterprise Intelligence Layer.

Wires together all intelligence engines and provides a unified API for
collecting metrics, computing health scores, generating forecasts,
recommendations, risks, capacity plans, digital twin snapshots, and
intelligence reports.

Usage:
    manager = IntelligenceManager()
    health = await manager.compute_health()
    forecasts = await manager.forecast()
    recommendations = await manager.optimize()
    report = await manager.generate_report("daily_executive")
"""

from __future__ import annotations

import time
from datetime import UTC, datetime
from typing import Any

from core.logging import get_logger
from services.intelligence.digital_twin import DigitalTwinEngine
from services.intelligence.engines import (
    CapacityPlanningEngine,
    CostIntelligenceEngine,
    OptimizationEngine,
    PredictiveAnalyticsEngine,
    RiskAnalysisEngine,
)
from services.intelligence.executive_engine import ExecutiveIntelligenceEngine
from services.intelligence.models import (
    CapacityForecast,
    CostBreakdown,
    CostForecast,
    DigitalTwinSnapshot,
    EnterpriseHealthScore,
    ForecastResult,
    IntelligenceReport,
    IntelligenceReportType,
    OperationalMetrics,
    OptimizationRecommendation,
    RiskAssessment,
)
from services.intelligence.reporting import ReportingEngine

_log = get_logger(__name__)

__all__ = ["IntelligenceManager"]


class IntelligenceManager:
    """Top-level facade for the Enterprise Intelligence Layer.

    Collects operational metrics from the running system and feeds them
    to the intelligence engines. All methods are async.
    """

    def __init__(self) -> None:
        self.executive = ExecutiveIntelligenceEngine()
        self.predictive = PredictiveAnalyticsEngine()
        self.optimization = OptimizationEngine()
        self.risk = RiskAnalysisEngine()
        self.capacity = CapacityPlanningEngine()
        self.cost = CostIntelligenceEngine()
        self.digital_twin = DigitalTwinEngine()
        self.reporting = ReportingEngine()
        self._start_time = time.time()
        self._metrics_history: list[OperationalMetrics] = []

    async def collect_metrics(self) -> OperationalMetrics:
        """Collect live operational metrics from the system.

        In a production system, this would query the actual subsystems
        (MissionManager, AgentRegistry, ModelRouter, etc.). For testing
        and when subsystems aren't initialized, it returns default metrics.
        """
        metrics = OperationalMetrics()
        metrics.uptime_s = time.time() - self._start_time

        # Try to collect from MissionManager
        try:
            from services.organization import MissionManager
            mgr = MissionManager()
            await mgr.start()
            summary = await mgr.get_mission_summary()
            metrics.total_missions = summary.total_missions
            metrics.active_missions = summary.by_status.get("executing", 0) + summary.by_status.get("planning", 0)
            metrics.total_wbs_nodes = summary.total_wbs_nodes
            metrics.completed_wbs_nodes = summary.total_completed_nodes
            metrics.total_budget_usd = summary.total_budget_usd
            metrics.total_spent_usd = summary.total_spent_usd
            metrics.total_artifacts = summary.total_artifacts
            metrics.total_decisions = summary.total_decisions
            if summary.total_missions > 0:
                metrics.avg_mission_completion_pct = (
                    summary.total_completed_nodes / max(1, summary.total_wbs_nodes) * 100
                )
        except Exception:
            pass  # Mission system not available

        # Try to collect from LearningEngine
        try:
            from services.experience import LearningEngine
            engine = LearningEngine()
            stats = await engine.learning_stats()
            metrics.total_experiences = stats.total_experiences
            metrics.avg_agent_reliability = stats.overall_success_rate
            metrics.avg_provider_reliability = stats.overall_success_rate
            metrics.total_tokens_consumed = stats.total_tokens
        except Exception:
            pass

        # Try to collect from ResourceManager
        try:
            from services.organization import ResourceManager
            rm = ResourceManager()
            util = await rm.get_utilization()
            metrics.active_agents = util.total_agents_assigned
            metrics.queue_depth = util.total_concurrent_tasks
        except Exception:
            pass

        # Store in history
        self._metrics_history.append(metrics)
        if len(self._metrics_history) > 100:
            self._metrics_history = self._metrics_history[-100:]

        return metrics

    async def compute_health(self) -> EnterpriseHealthScore:
        """Compute the enterprise health score."""
        metrics = await self.collect_metrics()
        success_history = [1.0] * 10  # placeholder — would come from experience
        cost_history = [metrics.total_spent_usd] * 5
        return self.executive.compute_health(
            metrics,
            success_rate_history=success_history,
            cost_history=cost_history,
            learning_rate=float(metrics.total_experiences),
        )

    async def forecast(self) -> list[ForecastResult]:
        """Generate forecasts."""
        metrics = await self.collect_metrics()
        return self.predictive.forecast_all(metrics)

    async def optimize(self) -> list[OptimizationRecommendation]:
        """Generate optimization recommendations."""
        metrics = await self.collect_metrics()
        return self.optimization.generate_all(metrics)

    async def assess_risks(self) -> list[RiskAssessment]:
        """Detect and assess risks."""
        metrics = await self.collect_metrics()
        forecasts = await self.forecast()
        return self.risk.assess_all(metrics, forecasts)

    async def risk_heat_map(self) -> dict[str, Any]:
        """Generate a risk heat map."""
        risks = await self.assess_risks()
        return self.risk.heat_map(risks)

    async def forecast_capacity(self) -> list[CapacityForecast]:
        """Forecast capacity for all resources."""
        metrics = await self.collect_metrics()
        return self.capacity.forecast_capacity(metrics)

    async def analyze_cost(self) -> CostBreakdown:
        """Analyze costs across dimensions."""
        metrics = await self.collect_metrics()
        return self.cost.analyze(metrics)

    async def forecast_cost(self) -> CostForecast:
        """Forecast future costs."""
        metrics = await self.collect_metrics()
        return self.cost.forecast(metrics)

    async def digital_twin_snapshot(self) -> DigitalTwinSnapshot:
        """Build a digital twin snapshot."""
        metrics = await self.collect_metrics()
        health = await self.compute_health()
        component_health = [c.to_dict() for c in health.component_health]
        return self.digital_twin.build_snapshot(metrics, component_health=component_health)

    async def generate_report(
        self,
        report_type: str = IntelligenceReportType.DAILY_EXECUTIVE.value,
    ) -> IntelligenceReport:
        """Generate an intelligence report."""
        metrics = await self.collect_metrics()
        health = await self.compute_health()
        forecasts = await self.forecast()
        recommendations = await self.optimize()
        risks = await self.assess_risks()
        capacity = await self.forecast_capacity()
        cost = await self.analyze_cost()
        return self.reporting.generate(
            report_type,
            health=health,
            metrics=metrics,
            forecasts=forecasts,
            recommendations=recommendations,
            risks=risks,
            capacity=capacity,
            cost=cost,
        )

    async def get_all_intelligence(self) -> dict[str, Any]:
        """Get all intelligence data in a single response (for the dashboard)."""
        metrics = await self.collect_metrics()
        health = await self.compute_health()
        forecasts = await self.forecast()
        recommendations = await self.optimize()
        risks = await self.assess_risks()
        capacity = await self.forecast_capacity()
        cost = await self.analyze_cost()
        twin = await self.digital_twin_snapshot()
        return {
            "metrics": metrics.to_dict(),
            "health": health.to_dict(),
            "forecasts": [f.to_dict() for f in forecasts],
            "recommendations": [r.to_dict() for r in recommendations],
            "risks": [r.to_dict() for r in risks],
            "risk_heat_map": self.risk.heat_map(risks),
            "capacity": [c.to_dict() for c in capacity],
            "cost": cost.to_dict(),
            "digital_twin": twin.to_dict(),
            "generated_at": datetime.now(UTC).isoformat(),
        }
