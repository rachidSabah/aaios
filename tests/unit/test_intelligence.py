"""Tests for the Enterprise Intelligence Layer (v3.1)."""

from __future__ import annotations

import pytest

from services.intelligence import (
    CapacityPlanningEngine,
    CostIntelligenceEngine,
    DigitalTwinEngine,
    EnterpriseHealthScore,
    ExecutiveIntelligenceEngine,
    ForecastType,
    IntelligenceManager,
    IntelligenceReportType,
    OperationalMetrics,
    OptimizationEngine,
    OptimizationType,
    PredictiveAnalyticsEngine,
    ReportingEngine,
    RiskAnalysisEngine,
)


def _make_metrics(
    *,
    total_missions: int = 10,
    active_missions: int = 3,
    total_agents: int = 5,
    active_agents: int = 3,
    total_budget_usd: float = 1000.0,
    total_spent_usd: float = 500.0,
    memory_usage_mb: float = 2048.0,
    cpu_usage_pct: float = 45.0,
    queue_depth: int = 5,
    open_risks: int = 2,
    avg_agent_reliability: float = 0.9,
    avg_provider_reliability: float = 0.85,
    total_wbs_nodes: int = 50,
    completed_wbs_nodes: int = 35,
    total_experiences: int = 100,
    total_artifacts: int = 15,
    total_decisions: int = 20,
    uptime_s: float = 7200.0,
    event_bus_throughput_per_s: float = 150.0,
) -> OperationalMetrics:
    return OperationalMetrics(
        total_missions=total_missions,
        active_missions=active_missions,
        total_agents=total_agents,
        active_agents=active_agents,
        total_budget_usd=total_budget_usd,
        total_spent_usd=total_spent_usd,
        memory_usage_mb=memory_usage_mb,
        cpu_usage_pct=cpu_usage_pct,
        queue_depth=queue_depth,
        open_risks=open_risks,
        avg_agent_reliability=avg_agent_reliability,
        avg_provider_reliability=avg_provider_reliability,
        total_wbs_nodes=total_wbs_nodes,
        completed_wbs_nodes=completed_wbs_nodes,
        total_experiences=total_experiences,
        total_artifacts=total_artifacts,
        total_decisions=total_decisions,
        uptime_s=uptime_s,
        event_bus_throughput_per_s=event_bus_throughput_per_s,
    )


# ============================================================
# Executive Intelligence Engine
# ============================================================


@pytest.mark.offline
class TestExecutiveIntelligenceEngine:
    """Executive Intelligence Engine tests."""

    def test_compute_health_healthy(self) -> None:
        engine = ExecutiveIntelligenceEngine()
        metrics = _make_metrics()
        metrics.avg_mission_completion_pct = 95.0
        health = engine.compute_health(metrics)
        assert health.overall_score > 0.7
        assert health.grade in ("A+", "A", "B+", "B", "C+", "C")

    def test_compute_health_degraded(self) -> None:
        engine = ExecutiveIntelligenceEngine()
        metrics = _make_metrics(
            avg_agent_reliability=0.5,
            avg_provider_reliability=0.5,
            memory_usage_mb=7000,
            cpu_usage_pct=90,
            queue_depth=80,
        )
        health = engine.compute_health(metrics)
        assert health.overall_score < 0.8

    def test_health_score_weights(self) -> None:
        score = EnterpriseHealthScore()
        assert sum(score.WEIGHTS.values()) == pytest.approx(1.0, abs=0.01)

    def test_grade_thresholds(self) -> None:
        score = EnterpriseHealthScore()
        score.operational = 1.0
        score.mission = 1.0
        score.agent_efficiency = 1.0
        score.provider_efficiency = 1.0
        score.workflow_quality = 1.0
        score.execution_success = 1.0
        score.risk_level = 1.0
        score.reliability = 1.0
        score.cost_efficiency = 1.0
        score.learning_velocity = 1.0
        score.innovation = 1.0
        assert score.overall_score == pytest.approx(1.0)
        assert score.grade == "A+"

    def test_component_health_generated(self) -> None:
        engine = ExecutiveIntelligenceEngine()
        metrics = _make_metrics()
        health = engine.compute_health(metrics)
        assert len(health.component_health) >= 5
        assert any(c.component == "kernel" for c in health.component_health)


# ============================================================
# Predictive Analytics Engine
# ============================================================


@pytest.mark.offline
class TestPredictiveAnalyticsEngine:
    """Predictive Analytics Engine tests."""

    def test_forecast_all(self) -> None:
        engine = PredictiveAnalyticsEngine()
        metrics = _make_metrics()
        forecasts = engine.forecast_all(metrics)
        assert len(forecasts) > 0
        # Each forecast should have valid fields
        for f in forecasts:
            assert 0.0 <= f.probability <= 1.0
            assert f.confidence in ("high", "medium", "low")
            assert f.prediction

    def test_forecast_mission_failure(self) -> None:
        engine = PredictiveAnalyticsEngine()
        metrics = _make_metrics(open_risks=10, queue_depth=80)
        f = engine.forecast_mission_failure(metrics, trend=[0.5, 0.4, 0.3])
        assert f.forecast_type == ForecastType.MISSION_FAILURE.value
        assert f.probability > 0.3

    def test_forecast_budget_overrun(self) -> None:
        engine = PredictiveAnalyticsEngine()
        metrics = _make_metrics(total_spent_usd=850, total_budget_usd=1000)
        f = engine.forecast_budget_overrun(metrics, spend_rate_per_day=50.0)
        assert f.probability > 0.5

    def test_forecast_memory_saturation(self) -> None:
        engine = PredictiveAnalyticsEngine()
        metrics = _make_metrics(memory_usage_mb=7500)
        f = engine.forecast_memory_saturation(metrics)
        assert f.probability > 0.3
        assert f.confidence == "high"

    def test_forecast_queue_congestion(self) -> None:
        engine = PredictiveAnalyticsEngine()
        metrics = _make_metrics(queue_depth=60)
        f = engine.forecast_queue_congestion(metrics)
        assert f.probability > 0.4

    def test_forecast_provider_outage(self) -> None:
        engine = PredictiveAnalyticsEngine()
        metrics = _make_metrics(avg_provider_reliability=0.6)
        f = engine.forecast_provider_outage(metrics)
        assert f.probability > 0.2

    def test_forecast_agent_degradation(self) -> None:
        engine = PredictiveAnalyticsEngine()
        metrics = _make_metrics(avg_agent_reliability=0.6)
        f = engine.forecast_agent_degradation(metrics)
        assert f.probability > 0.2

    def test_forecast_recommended_actions(self) -> None:
        engine = PredictiveAnalyticsEngine()
        metrics = _make_metrics(queue_depth=80)
        f = engine.forecast_queue_congestion(metrics)
        assert len(f.recommended_actions) > 0

    def test_forecast_all_filters_low_probability(self) -> None:
        engine = PredictiveAnalyticsEngine()
        metrics = _make_metrics()
        forecasts = engine.forecast_all(metrics)
        for f in forecasts:
            assert f.probability > 0.05


# ============================================================
# Optimization Engine
# ============================================================


@pytest.mark.offline
class TestOptimizationEngine:
    """Optimization Engine tests."""

    def test_generate_all(self) -> None:
        engine = OptimizationEngine()
        metrics = _make_metrics()
        recs = engine.generate_all(metrics)
        assert isinstance(recs, list)

    def test_recommend_routing(self) -> None:
        engine = OptimizationEngine()
        metrics = _make_metrics()
        recs = engine.recommend_routing(
            metrics,
            agent_scores={"agent-a": 0.9, "agent-b": 0.5},
        )
        assert len(recs) >= 1
        assert recs[0].optimization_type == OptimizationType.ROUTING.value

    def test_recommend_concurrency(self) -> None:
        engine = OptimizationEngine()
        metrics = _make_metrics(queue_depth=50, cpu_usage_pct=40)
        recs = engine.recommend_concurrency(metrics)
        assert len(recs) >= 1
        assert "increase" in recs[0].title.lower() or "concurrency" in recs[0].title.lower()

    def test_recommend_caching(self) -> None:
        engine = OptimizationEngine()
        metrics = _make_metrics(total_experiences=200)
        recs = engine.recommend_caching(metrics)
        assert len(recs) >= 1

    def test_recommendations_never_auto_apply(self) -> None:
        engine = OptimizationEngine()
        metrics = _make_metrics()
        recs = engine.generate_all(metrics)
        for r in recs:
            assert r.status == "pending"


# ============================================================
# Risk Analysis Engine
# ============================================================


@pytest.mark.offline
class TestRiskAnalysisEngine:
    """Risk Analysis Engine tests."""

    def test_assess_all(self) -> None:
        engine = RiskAnalysisEngine()
        metrics = _make_metrics()
        risks = engine.assess_all(metrics)
        assert isinstance(risks, list)
        for r in risks:
            assert 0.0 <= r.probability <= 1.0
            assert 0.0 <= r.impact <= 1.0
            assert r.risk_score == pytest.approx(r.probability * r.impact)

    def test_budget_risk_high(self) -> None:
        engine = RiskAnalysisEngine()
        metrics = _make_metrics(total_spent_usd=900, total_budget_usd=1000)
        risk = engine.assess_budget_risk(metrics)
        assert risk.probability > 0.5

    def test_capacity_risk(self) -> None:
        engine = RiskAnalysisEngine()
        metrics = _make_metrics(total_agents=5, active_agents=5)
        risk = engine.assess_capacity_risk(metrics)
        assert risk.probability > 0.3

    def test_heat_map(self) -> None:
        engine = RiskAnalysisEngine()
        metrics = _make_metrics()
        risks = engine.assess_all(metrics)
        heat_map = engine.heat_map(risks)
        assert "by_level" in heat_map
        assert "total_risks" in heat_map
        assert heat_map["total_risks"] == len(risks)

    def test_risks_from_forecasts(self) -> None:
        engine = RiskAnalysisEngine()
        metrics = _make_metrics()
        from services.intelligence.models import ForecastResult

        forecasts = [
            ForecastResult(probability=0.8, prediction="High risk forecast"),
            ForecastResult(probability=0.1, prediction="Low risk forecast"),
        ]
        risks = engine.assess_all(metrics, forecasts)
        # High-probability forecast should become a risk
        assert any("high risk forecast" in r.description.lower() for r in risks)


# ============================================================
# Capacity Planning Engine
# ============================================================


@pytest.mark.offline
class TestCapacityPlanningEngine:
    """Capacity Planning Engine tests."""

    def test_forecast_capacity(self) -> None:
        engine = CapacityPlanningEngine()
        metrics = _make_metrics()
        caps = engine.forecast_capacity(metrics)
        assert len(caps) >= 4  # agents, budget, memory, cpu
        resources = {c.resource for c in caps}
        assert "agents" in resources
        assert "budget" in resources
        assert "memory" in resources

    def test_capacity_utilization(self) -> None:
        engine = CapacityPlanningEngine()
        metrics = _make_metrics(active_agents=8, total_agents=10)
        caps = engine.forecast_capacity(metrics)
        agent_cap = next(c for c in caps if c.resource == "agents")
        assert agent_cap.utilization_pct == pytest.approx(80.0, abs=1)

    def test_exhaustion_eta(self) -> None:
        engine = CapacityPlanningEngine()
        metrics = _make_metrics(total_spent_usd=900, total_budget_usd=1000)
        caps = engine.forecast_capacity(metrics, growth_rate_per_day=0.05)
        budget_cap = next(c for c in caps if c.resource == "budget")
        assert budget_cap.exhaustion_eta is not None


# ============================================================
# Cost Intelligence Engine
# ============================================================


@pytest.mark.offline
class TestCostIntelligenceEngine:
    """Cost Intelligence Engine tests."""

    def test_analyze(self) -> None:
        engine = CostIntelligenceEngine()
        metrics = _make_metrics()
        cost = engine.analyze(
            metrics,
            by_provider={"openai": 300, "anthropic": 200},
            by_agent={"agent-a": 250, "agent-b": 250},
        )
        assert cost.total_spent_usd == metrics.total_spent_usd
        assert cost.by_provider["openai"] == 300
        assert cost.cost_efficiency_score > 0

    def test_forecast(self) -> None:
        engine = CostIntelligenceEngine()
        metrics = _make_metrics()
        forecast = engine.forecast(metrics, spend_rate_per_day=50.0)
        assert forecast.projected_daily_spend_usd == 50.0
        assert forecast.projected_weekly_spend_usd == 350.0
        assert forecast.projected_monthly_spend_usd == 1500.0


# ============================================================
# Digital Twin
# ============================================================


@pytest.mark.offline
class TestDigitalTwinEngine:
    """Digital Twin Engine tests."""

    def test_build_snapshot(self) -> None:
        engine = DigitalTwinEngine()
        metrics = _make_metrics()
        snapshot = engine.build_snapshot(metrics)
        assert len(snapshot.nodes) >= 10
        assert len(snapshot.edges) >= 8
        node_types = {n.node_type for n in snapshot.nodes}
        assert "kernel" in node_types
        assert "supervisor" in node_types
        assert "mission_manager" in node_types
        assert "agent_registry" in node_types
        assert "model_router" in node_types

    def test_snapshot_overall_health(self) -> None:
        engine = DigitalTwinEngine()
        metrics = _make_metrics()
        snapshot = engine.build_snapshot(metrics)
        assert 0.0 <= snapshot.overall_health <= 1.0

    def test_snapshot_to_dict(self) -> None:
        engine = DigitalTwinEngine()
        metrics = _make_metrics()
        snapshot = engine.build_snapshot(metrics)
        d = snapshot.to_dict()
        assert "nodes" in d
        assert "edges" in d
        assert d["node_count"] == len(snapshot.nodes)


# ============================================================
# Reporting Engine
# ============================================================


@pytest.mark.offline
class TestReportingEngine:
    """Reporting Engine tests."""

    def test_generate_daily_report(self) -> None:
        engine = ReportingEngine()
        exec_engine = ExecutiveIntelligenceEngine()
        metrics = _make_metrics()
        health = exec_engine.compute_health(metrics)
        report = engine.generate(
            IntelligenceReportType.DAILY_EXECUTIVE.value,
            health=health,
            metrics=metrics,
        )
        assert report.report_type == IntelligenceReportType.DAILY_EXECUTIVE.value
        assert len(report.summary) > 0
        assert len(report.key_findings) > 0
        assert len(report.action_items) > 0

    def test_generate_with_forecasts_and_risks(self) -> None:
        engine = ReportingEngine()
        exec_engine = ExecutiveIntelligenceEngine()
        pred_engine = PredictiveAnalyticsEngine()
        risk_engine = RiskAnalysisEngine()
        opt_engine = OptimizationEngine()
        metrics = _make_metrics(queue_depth=60, open_risks=5)
        health = exec_engine.compute_health(metrics)
        forecasts = pred_engine.forecast_all(metrics)
        risks = risk_engine.assess_all(metrics, forecasts)
        recs = opt_engine.generate_all(metrics)
        report = engine.generate(
            IntelligenceReportType.WEEKLY_OPERATIONS.value,
            health=health,
            metrics=metrics,
            forecasts=forecasts,
            recommendations=recs,
            risks=risks,
        )
        assert len(report.forecasts) > 0
        assert len(report.risks) > 0
        assert len(report.key_findings) > 0


# ============================================================
# IntelligenceManager (Integration)
# ============================================================


@pytest.mark.offline
class TestIntelligenceManager:
    """IntelligenceManager facade tests."""

    async def test_collect_metrics(self) -> None:
        mgr = IntelligenceManager()
        metrics = await mgr.collect_metrics()
        assert metrics.uptime_s > 0

    async def test_compute_health(self) -> None:
        mgr = IntelligenceManager()
        health = await mgr.compute_health()
        assert 0.0 <= health.overall_score <= 1.0
        assert health.grade in ("A+", "A", "B+", "B", "C+", "C", "D", "F")

    async def test_forecast(self) -> None:
        mgr = IntelligenceManager()
        forecasts = await mgr.forecast()
        assert isinstance(forecasts, list)

    async def test_optimize(self) -> None:
        mgr = IntelligenceManager()
        recs = await mgr.optimize()
        assert isinstance(recs, list)

    async def test_assess_risks(self) -> None:
        mgr = IntelligenceManager()
        risks = await mgr.assess_risks()
        assert isinstance(risks, list)

    async def test_risk_heat_map(self) -> None:
        mgr = IntelligenceManager()
        heat_map = await mgr.risk_heat_map()
        assert "by_level" in heat_map
        assert "total_risks" in heat_map

    async def test_forecast_capacity(self) -> None:
        mgr = IntelligenceManager()
        caps = await mgr.forecast_capacity()
        assert len(caps) >= 4

    async def test_analyze_cost(self) -> None:
        mgr = IntelligenceManager()
        cost = await mgr.analyze_cost()
        assert cost.total_spent_usd >= 0

    async def test_digital_twin(self) -> None:
        mgr = IntelligenceManager()
        twin = await mgr.digital_twin_snapshot()
        assert len(twin.nodes) >= 10

    async def test_generate_report(self) -> None:
        mgr = IntelligenceManager()
        report = await mgr.generate_report()
        assert report.report_type == IntelligenceReportType.DAILY_EXECUTIVE.value
        assert len(report.summary) > 0

    async def test_get_all_intelligence(self) -> None:
        mgr = IntelligenceManager()
        data = await mgr.get_all_intelligence()
        assert "metrics" in data
        assert "health" in data
        assert "forecasts" in data
        assert "digital_twin" in data


# ============================================================
# Forecast Validation Tests
# ============================================================


@pytest.mark.offline
class TestForecastValidation:
    """Validate that forecasts are reasonable."""

    def test_all_forecast_types_covered(self) -> None:
        engine = PredictiveAnalyticsEngine()
        metrics = _make_metrics()
        forecasts = engine.forecast_all(metrics)
        types = {f.forecast_type for f in forecasts}
        # Should cover most forecast types
        expected_types = {
            ForecastType.MISSION_FAILURE.value,
            ForecastType.WORKFLOW_BOTTLENECK.value,
            ForecastType.QUEUE_CONGESTION.value,
            ForecastType.BUDGET_OVERRUN.value,
        }
        assert expected_types.issubset(types)

    def test_forecast_probabilities_bounded(self) -> None:
        engine = PredictiveAnalyticsEngine()
        metrics = _make_metrics()
        forecasts = engine.forecast_all(metrics)
        for f in forecasts:
            assert 0.0 <= f.probability <= 0.95  # capped at 95%

    def test_forecast_confidence_correlates_with_probability(self) -> None:
        engine = PredictiveAnalyticsEngine()
        metrics = _make_metrics(queue_depth=80, memory_usage_mb=7500)
        forecasts = engine.forecast_all(metrics)
        for f in forecasts:
            if f.probability > 0.4:
                assert f.confidence in ("high", "medium")


# ============================================================
# Stress Tests
# ============================================================


@pytest.mark.offline
class TestIntelligenceStress:
    """Stress tests for the intelligence system."""

    def test_repeated_health_computation(self) -> None:
        engine = ExecutiveIntelligenceEngine()
        metrics = _make_metrics()
        for _ in range(100):
            health = engine.compute_health(metrics)
            assert health.overall_score > 0

    def test_repeated_forecast_generation(self) -> None:
        engine = PredictiveAnalyticsEngine()
        metrics = _make_metrics()
        for _ in range(50):
            forecasts = engine.forecast_all(metrics)
            assert len(forecasts) > 0

    async def test_repeated_full_analysis(self) -> None:
        mgr = IntelligenceManager()
        for _ in range(5):
            data = await mgr.get_all_intelligence()
            assert "health" in data
