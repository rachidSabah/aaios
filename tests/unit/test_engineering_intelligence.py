"""Tests for Engineering Intelligence (v5.2 Part 1B-1).

Tests PlanningEngine, MetricsEngine, ArchitectureAnalysisEngine,
ImpactAnalysisEngine, RecommendationEngine, RiskEngine.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from services.engineering.intelligence import (
    ArchitectureAnalysisEngine,
    ImpactAnalysisEngine,
    MetricsEngine,
    PlanningEngine,
    RecommendationEngine,
    RiskEngine,
)


@pytest.mark.offline
class TestPlanningEngine:
    """PlanningEngine tests."""

    async def test_create_plan(self) -> None:
        engine = PlanningEngine()
        plan = await engine.create_plan(
            title="Test Plan",
            description="A test plan",
            requirements=["Build feature A", "Build feature B", "Test everything"],
        )
        assert plan.title == "Test Plan"
        assert len(plan.items) == 3
        assert plan.total_estimated_hours > 0
        assert plan.confidence > 0
        assert len(plan.assumptions) > 0
        assert len(plan.constraints) > 0
        assert plan.requires_approval is True

    async def test_critical_path(self) -> None:
        engine = PlanningEngine()
        plan = await engine.create_plan(
            title="CP Test",
            description="test",
            requirements=["A", "B", "C"],
        )
        # Add dependencies
        plan.items[1].dependencies = [plan.items[0].item_id]
        plan.items[2].dependencies = [plan.items[1].item_id]
        path = await engine.critical_path(plan)
        assert len(path) == 3
        assert path[0] == plan.items[0].item_id

    async def test_plan_has_risks(self) -> None:
        engine = PlanningEngine()
        plan = await engine.create_plan("T", "D", ["req1"])
        assert len(plan.risks) > 0


@pytest.mark.offline
class TestMetricsEngine:
    """MetricsEngine tests."""

    async def test_compute_metrics(self) -> None:
        engine = MetricsEngine()
        metrics = await engine.compute_metrics(Path())
        assert metrics.total_files > 0
        assert metrics.total_lines > 0
        assert metrics.total_functions > 0
        assert metrics.avg_cyclomatic_complexity > 0
        assert metrics.avg_maintainability_index >= 0
        assert metrics.test_coverage_pct >= 0
        assert metrics.documentation_coverage_pct >= 0
        assert metrics.comment_density >= 0
        assert metrics.risk_score >= 0
        assert metrics.engineering_maturity >= 0

    async def test_metrics_to_dict(self) -> None:
        engine = MetricsEngine()
        metrics = await engine.compute_metrics(Path())
        d = metrics.to_dict()
        assert "total_files" in d
        assert "avg_cyclomatic_complexity" in d
        assert "technical_debt_hours" in d
        assert "engineering_maturity" in d


@pytest.mark.offline
class TestArchitectureAnalysis:
    """ArchitectureAnalysisEngine tests."""

    async def test_analyze(self) -> None:
        engine = ArchitectureAnalysisEngine()
        result = await engine.analyze(Path())
        assert isinstance(result.god_classes, list)
        assert isinstance(result.layer_violations, list)
        assert isinstance(result.recommendations, list)
        assert len(result.recommendations) > 0

    async def test_to_dict(self) -> None:
        engine = ArchitectureAnalysisEngine()
        result = await engine.analyze(Path())
        d = result.to_dict()
        assert "god_classes" in d
        assert "layer_violations" in d
        assert "recommendations" in d


@pytest.mark.offline
class TestImpactAnalysis:
    """ImpactAnalysisEngine tests."""

    async def test_analyze_impact(self) -> None:
        engine = ImpactAnalysisEngine()
        result = await engine.analyze_impact(Path(), "services/engineering/models.py")
        assert isinstance(result.affected_modules, list)
        assert result.risk in ("low", "medium", "high")
        assert result.complexity in ("low", "medium", "high")
        assert result.testing_effort_hours >= 0
        assert result.confidence > 0
        assert result.reasoning != ""

    async def test_to_dict(self) -> None:
        engine = ImpactAnalysisEngine()
        result = await engine.analyze_impact(Path(), "core/event_bus/bus.py")
        d = result.to_dict()
        assert "affected_modules" in d
        assert "testing_effort_hours" in d
        assert "confidence" in d


@pytest.mark.offline
class TestRecommendationEngine:
    """RecommendationEngine tests."""

    async def test_recommend_all(self) -> None:
        from services.engineering.intelligence import ArchAnalysisResult, EngineeringMetrics

        metrics = EngineeringMetrics(
            avg_cyclomatic_complexity=15.0,
            test_coverage_pct=30.0,
            documentation_coverage_pct=20.0,
            risk_score=0.7,
        )
        arch = ArchAnalysisResult(
            god_classes=["BigClass"],
            layer_violations=[{"file": "test.py", "import": "surfaces.api"}],
        )
        engine = RecommendationEngine()
        recs = await engine.recommend_all(metrics, arch)
        assert len(recs) > 0
        for rec in recs:
            assert rec.requires_approval is True
            assert rec.confidence > 0
            assert rec.reasoning != ""
            assert rec.rollback_strategy != ""
            assert rec.estimated_effort_hours > 0
            d = rec.to_dict()
            assert "title" in d
            assert "category" in d
            assert "severity" in d

    async def test_no_recommendations_for_healthy_code(self) -> None:
        from services.engineering.intelligence import ArchAnalysisResult, EngineeringMetrics

        metrics = EngineeringMetrics(
            avg_cyclomatic_complexity=5.0,
            test_coverage_pct=90.0,
            documentation_coverage_pct=90.0,
            risk_score=0.2,
        )
        arch = ArchAnalysisResult()
        engine = RecommendationEngine()
        recs = await engine.recommend_all(metrics, arch)
        assert len(recs) == 0


@pytest.mark.offline
class TestRiskEngine:
    """RiskEngine tests."""

    async def test_assess_all(self) -> None:
        from services.engineering.intelligence import ArchAnalysisResult, EngineeringMetrics

        metrics = EngineeringMetrics(
            test_coverage_pct=30.0,
            avg_cyclomatic_complexity=15.0,
            technical_debt_hours=100.0,
            architecture_violations=10,
        )
        arch = ArchAnalysisResult(
            layer_violations=[{"file": "test.py"}],
        )
        engine = RiskEngine()
        risks = await engine.assess_all(metrics, arch)
        assert len(risks) > 0
        for risk in risks:
            assert risk.risk_score > 0
            assert risk.confidence > 0
            assert risk.mitigation_strategy != ""
            assert len(risk.alternative_approaches) > 0
            d = risk.to_dict()
            assert "risk_type" in d
            assert "mitigation_strategy" in d

    async def test_no_risks_for_healthy_code(self) -> None:
        from services.engineering.intelligence import ArchAnalysisResult, EngineeringMetrics

        metrics = EngineeringMetrics(
            test_coverage_pct=90.0,
            avg_cyclomatic_complexity=5.0,
            technical_debt_hours=10.0,
            architecture_violations=0,
        )
        arch = ArchAnalysisResult()
        engine = RiskEngine()
        risks = await engine.assess_all(metrics, arch)
        assert len(risks) == 0
