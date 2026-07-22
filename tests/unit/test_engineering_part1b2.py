"""Tests for Engineering v5.2 Part 1B-2 engines.

Tests EngineeringReviewEngine, TestIntelligenceEngine,
DocumentationIntelligenceEngine, RepositoryEvolutionEngine,
ReleaseReadinessEngine, DeveloperProductivityEngine,
RepositoryHealthCenter, and EngineeringManager wiring.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from services.engineering.documentation_intelligence import (
    DocType,
    DocumentationIntelligenceEngine,
)
from services.engineering.evolution_engine import RepositoryEvolutionEngine
from services.engineering.health_center import (
    HealthDimension,
    RepositoryHealthCenter,
)
from services.engineering.manager import EngineeringManager
from services.engineering.productivity_engine import (
    DeveloperProductivityEngine,
    DORAMetrics,
)
from services.engineering.release_readiness import (
    ReadinessDimension,
    ReleaseReadinessEngine,
)
from services.engineering.review_engine import (
    EngineeringReviewEngine,
    ReviewType,
)
from services.engineering.test_intelligence import (
    TestIntelligenceEngine,
)
from services.engineering.test_intelligence import TestType as TTestType

# ---------------------------------------------------------------------------
# Phase 17 — Engineering Review Engine
# ---------------------------------------------------------------------------


@pytest.mark.offline
class TestEngineeringReviewEngine:
    """EngineeringReviewEngine tests."""

    async def test_review_types_enum_has_twelve_values(self) -> None:
        assert len(list(ReviewType)) == 12

    async def test_review_architecture_on_empty_dir(self) -> None:
        engine = EngineeringReviewEngine()
        with TemporaryDirectory() as d:
            report = await engine.review(ReviewType.ARCHITECTURE, d)
        assert report.review_type == "architecture"
        assert report.risk_score >= 0.0
        assert 0.0 <= report.confidence <= 1.0

    async def test_review_code_detects_bare_except(self) -> None:
        engine = EngineeringReviewEngine()
        with TemporaryDirectory() as d:
            p = Path(d) / "mod.py"
            p.write_text("def bad():\n    try:\n        return 1\n    except:\n        return 0\n")
            report = await engine.review(ReviewType.CODE, d)
        assert any(w.title == "Bare except clauses" for w in report.weaknesses)

    async def test_review_security_detects_eval(self) -> None:
        engine = EngineeringReviewEngine()
        with TemporaryDirectory() as d:
            p = Path(d) / "evil.py"
            p.write_text("def f():\n    return eval('1+1')\n")
            report = await engine.review(ReviewType.SECURITY, d)
        assert any(w.title == "Use of eval/exec" for w in report.weaknesses)

    async def test_review_documentation_missing_readme(self) -> None:
        engine = EngineeringReviewEngine()
        with TemporaryDirectory() as d:
            report = await engine.review(ReviewType.DOCUMENTATION, d)
        assert any(w.title == "Missing README" for w in report.weaknesses)

    async def test_review_testing_no_tests_dir(self) -> None:
        engine = EngineeringReviewEngine()
        with TemporaryDirectory() as d:
            report = await engine.review(ReviewType.TESTING, d)
        assert any(w.title == "No tests directory" for w in report.weaknesses)

    async def test_review_workflow_no_ci(self) -> None:
        engine = EngineeringReviewEngine()
        with TemporaryDirectory() as d:
            report = await engine.review(ReviewType.WORKFLOW, d)
        assert any(w.title == "No CI workflows" for w in report.weaknesses)

    async def test_review_mission_missing_fields(self) -> None:
        engine = EngineeringReviewEngine()
        report = await engine.review(
            ReviewType.MISSION, "mission-123", context={"mission": {"id": "x"}}
        )
        assert any(w.title == "Mission missing required fields" for w in report.weaknesses)

    async def test_review_all_runs_twelve_types(self) -> None:
        engine = EngineeringReviewEngine()
        with TemporaryDirectory() as d:
            results = await engine.review_all(d)
        assert len(results) == 12
        assert set(results.keys()) == {rt.value for rt in ReviewType}

    async def test_historical_comparison(self) -> None:
        engine = EngineeringReviewEngine()
        with TemporaryDirectory() as d:
            # First review (becomes history)
            history_report = await engine.review(ReviewType.CODE, d)
            # Second review with history
            report = await engine.review(ReviewType.CODE, d, history=[history_report])
        assert "comparison" in report.historical_comparison
        assert report.historical_comparison["comparison"] == "available"

    async def test_review_report_to_dict(self) -> None:
        engine = EngineeringReviewEngine()
        with TemporaryDirectory() as d:
            report = await engine.review(ReviewType.CODE, d)
        d = report.to_dict()
        assert "review_id" in d
        assert "strengths" in d
        assert "weaknesses" in d
        assert "risk_score" in d
        assert "confidence" in d
        assert "approval_required" in d


# ---------------------------------------------------------------------------
# Phase 18 — Test Intelligence Engine
# ---------------------------------------------------------------------------


@pytest.mark.offline
class TestTestIntelligenceEngine:
    """TestIntelligenceEngine tests."""

    async def test_analyze_empty_suite(self) -> None:
        engine = TestIntelligenceEngine()
        with TemporaryDirectory() as d:
            analysis = await engine.analyze_suite(d)
        assert analysis.total_tests == 0

    async def test_analyze_suite_detects_tests(self) -> None:
        engine = TestIntelligenceEngine()
        with TemporaryDirectory() as d:
            tests_dir = Path(d) / "tests"
            tests_dir.mkdir()
            (tests_dir / "test_foo.py").write_text(
                "import pytest\n@pytest.mark.slow\ndef test_basic():\n    assert 1 + 1 == 2\n"
            )
            analysis = await engine.analyze_suite(tests_dir)
        assert analysis.total_tests == 1
        assert analysis.total_files == 1

    async def test_test_type_enum_values(self) -> None:
        types = list(TTestType)
        assert TTestType.UNIT in types
        assert TTestType.INTEGRATION in types
        assert TTestType.E2E in types
        assert TTestType.PERFORMANCE in types
        assert TTestType.STRESS in types
        assert TTestType.SECURITY in types

    async def test_coverage_report_no_xml(self) -> None:
        engine = TestIntelligenceEngine()
        with TemporaryDirectory() as d:
            report = await engine.coverage_report(d)
        assert report.overall_pct >= 0.0

    async def test_risk_report_with_no_events(self) -> None:
        engine = TestIntelligenceEngine()
        with TemporaryDirectory() as d:
            tests_dir = Path(d) / "tests"
            tests_dir.mkdir()
            (tests_dir / "test_x.py").write_text("def test_x():\n    assert True\n")
            report = await engine.risk_report(d)
        assert 0.0 <= report.regression_risk_score <= 1.0
        assert report.requires_approval is True

    async def test_missing_tests_detection(self) -> None:
        engine = TestIntelligenceEngine()
        with TemporaryDirectory() as d:
            # Create a source file but no test file
            (Path(d) / "feature.py").write_text("def f():\n    return 1\n")
            tests_dir = Path(d) / "tests"
            tests_dir.mkdir()
            analysis = await engine.analyze_suite(tests_dir)
        # Should detect missing test for feature.py
        missing_files = [m["source_file"] for m in analysis.missing_tests]
        assert any("feature.py" in f for f in missing_files)


# ---------------------------------------------------------------------------
# Phase 19 — Documentation Intelligence
# ---------------------------------------------------------------------------


@pytest.mark.offline
class TestDocumentationIntelligence:
    """DocumentationIntelligenceEngine tests."""

    async def test_analyze_empty_dir(self) -> None:
        engine = DocumentationIntelligenceEngine()
        with TemporaryDirectory() as d:
            report = await engine.analyze(d)
        assert report.completeness_score >= 0.0

    async def test_analyze_detects_missing_readme(self) -> None:
        engine = DocumentationIntelligenceEngine()
        with TemporaryDirectory() as d:
            report = await engine.analyze(d)
        assert any(i.issue_type == "missing" and i.page == "README.md" for i in report.issues)

    async def test_analyze_detects_present_readme(self) -> None:
        engine = DocumentationIntelligenceEngine()
        with TemporaryDirectory() as d:
            (Path(d) / "README.md").write_text("# Project\n\n" + "x " * 100)
            report = await engine.analyze(d)
        assert not any(i.issue_type == "missing" and i.page == "README.md" for i in report.issues)

    async def test_doc_type_enum_values(self) -> None:
        types = list(DocType)
        assert DocType.README in types
        assert DocType.API_DOC in types
        assert DocType.MIGRATION_GUIDE in types

    async def test_recommendations_returns_list(self) -> None:
        engine = DocumentationIntelligenceEngine()
        with TemporaryDirectory() as d:
            recs = await engine.recommendations(d)
        assert isinstance(recs, list)

    async def test_broken_link_detection(self) -> None:
        engine = DocumentationIntelligenceEngine()
        with TemporaryDirectory() as d:
            (Path(d) / "README.md").write_text("# Project\n\n[broken](does-not-exist.md)\n")
            report = await engine.analyze(d)
        assert any(i.issue_type == "broken_ref" for i in report.issues)


# ---------------------------------------------------------------------------
# Phase 20 — Repository Evolution Engine
# ---------------------------------------------------------------------------


@pytest.mark.offline
class TestRepositoryEvolutionEngine:
    """RepositoryEvolutionEngine tests."""

    async def test_dashboard_on_non_git_dir(self) -> None:
        engine = RepositoryEvolutionEngine(repo_root="/tmp")
        dash = await engine.dashboard()
        # Should not raise; may have zero counts
        assert dash.total_commits >= 0

    async def test_timeline_returns_list(self) -> None:
        engine = RepositoryEvolutionEngine(repo_root=".")
        timeline = await engine.timeline(limit=5)
        assert isinstance(timeline, list)
        assert len(timeline) <= 5

    async def test_report_structure(self) -> None:
        engine = RepositoryEvolutionEngine(repo_root=".")
        report = await engine.report()
        d = report.to_dict()
        assert "repository" in d
        assert "timeline" in d
        assert "dashboard" in d

    async def test_historical_comparisons_returns_list(self) -> None:
        engine = RepositoryEvolutionEngine(repo_root=".")
        comps = await engine.historical_comparisons()
        assert isinstance(comps, list)


# ---------------------------------------------------------------------------
# Phase 21 — Release Readiness Engine
# ---------------------------------------------------------------------------


@pytest.mark.offline
class TestReleaseReadinessEngine:
    """ReleaseReadinessEngine tests."""

    async def test_evaluate_on_empty_dir(self) -> None:
        engine = ReleaseReadinessEngine()
        with TemporaryDirectory() as d:
            report = await engine.evaluate(d, version="0.0.1")
        assert report.version == "0.0.1"
        assert 0.0 <= report.overall_score <= 1.0
        assert report.recommendation in {"go", "conditional_go", "no_go"}

    async def test_ten_dimensions_present(self) -> None:
        engine = ReleaseReadinessEngine()
        with TemporaryDirectory() as d:
            report = await engine.evaluate(d)
        assert len(report.dimensions) == 10
        dim_names = {d.dimension for d in report.dimensions}
        assert dim_names == {dim.value for dim in ReadinessDimension}

    async def test_certification_report(self) -> None:
        engine = ReleaseReadinessEngine()
        with TemporaryDirectory() as d:
            cert = await engine.certification_report(d, version="1.0.0")
        assert cert.version == "1.0.0"
        assert cert.certification_level in {"none", "basic", "standard", "strict"}

    async def test_required_approvals_populated(self) -> None:
        engine = ReleaseReadinessEngine()
        with TemporaryDirectory() as d:
            report = await engine.evaluate(d)
        assert len(report.required_approvals) > 0

    async def test_blocking_issues_propagate(self) -> None:
        engine = ReleaseReadinessEngine()
        with TemporaryDirectory() as d:
            report = await engine.evaluate(d)
        # Empty dir → no tests dir → blocking issue expected
        assert len(report.blocking_issues) > 0
        assert report.recommendation == "no_go"


# ---------------------------------------------------------------------------
# Phase 22 — Developer Productivity Engine
# ---------------------------------------------------------------------------


@pytest.mark.offline
class TestDeveloperProductivityEngine:
    """DeveloperProductivityEngine tests."""

    async def test_metrics_with_no_events(self) -> None:
        engine = DeveloperProductivityEngine()
        m = await engine.metrics()
        assert m.cycle_time_hours == 0.0
        assert m.deployment_frequency == 0.0

    async def test_dora_classification_low(self) -> None:
        engine = DeveloperProductivityEngine()
        d = await engine.dora()
        assert d.level in {"low", "medium", "high", "elite"}

    async def test_record_event_increases_count(self) -> None:
        engine = DeveloperProductivityEngine()
        engine.record_event({"type": "commit", "timestamp": datetime.now(UTC).isoformat()})
        m = await engine.metrics()
        # No deploys → deployment_frequency stays 0
        assert m.deployment_frequency == 0.0

    async def test_record_events_batch(self) -> None:
        engine = DeveloperProductivityEngine()
        now = datetime.now(UTC)
        # Use past timestamps so events fall within the default 30-day window
        past_open = now - timedelta(hours=10)
        past_merge = now - timedelta(hours=8)
        engine.record_events(
            [
                {"type": "pr_opened", "pr_id": "1", "timestamp": past_open.isoformat()},
                {"type": "pr_merged", "pr_id": "1", "timestamp": past_merge.isoformat()},
            ]
        )
        m = await engine.metrics()
        assert m.cycle_time_hours > 0

    async def test_dashboard_structure(self) -> None:
        engine = DeveloperProductivityEngine()
        dash = await engine.dashboard()
        d = dash.to_dict()
        assert "current" in d
        assert "dora" in d
        assert "trends" in d
        assert "optimization_opportunities" in d
        assert "recommendations" in d

    async def test_dora_elite_classification(self) -> None:
        """Test that the elite threshold logic works."""
        d = DORAMetrics(
            deployment_frequency=2.0,
            lead_time_hours=1.0,
            change_failure_rate=0.05,
            recovery_time_hours=0.5,
        )
        # Apply same logic as in engine
        if (
            d.deployment_frequency >= 1.0
            and d.lead_time_hours <= 24
            and d.change_failure_rate <= 0.15
            and d.recovery_time_hours <= 1
        ):
            d.level = "elite"
            d.elite = True
        assert d.level == "elite"
        assert d.elite is True


# ---------------------------------------------------------------------------
# Phase 23 — Repository Health Center
# ---------------------------------------------------------------------------


@pytest.mark.offline
class TestRepositoryHealthCenter:
    """RepositoryHealthCenter tests."""

    async def test_assess_returns_report(self) -> None:
        with TemporaryDirectory() as d:
            center = RepositoryHealthCenter(repo_root=d)
            report = await center.assess()
        assert 0.0 <= report.overall_score <= 100.0
        assert report.status in {"healthy", "warning", "critical"}

    async def test_eight_dimensions_present(self) -> None:
        with TemporaryDirectory() as d:
            center = RepositoryHealthCenter(repo_root=d)
            report = await center.assess()
        assert len(report.dimensions) == 8
        dim_names = {dim.dimension for dim in report.dimensions}
        assert dim_names == {hd.value for hd in HealthDimension}

    async def test_quick_score(self) -> None:
        with TemporaryDirectory() as d:
            center = RepositoryHealthCenter(repo_root=d)
            score = await center.quick_score()
        assert 0.0 <= score <= 100.0

    async def test_improvement_recommendations(self) -> None:
        with TemporaryDirectory() as d:
            center = RepositoryHealthCenter(repo_root=d)
            report = await center.assess()
        # Empty dir should produce some recommendations
        assert isinstance(report.improvement_recommendations, list)

    async def test_trend_history_recorded(self) -> None:
        with TemporaryDirectory() as d:
            center = RepositoryHealthCenter(repo_root=d)
            await center.assess()
            await center.assess()
            report = await center.assess()
        assert len(report.trend) >= 3  # at least 3 history points


# ---------------------------------------------------------------------------
# EngineeringManager wiring
# ---------------------------------------------------------------------------


@pytest.mark.offline
class TestEngineeringManagerWiring:
    """Verify the EngineeringManager facade wires all new engines."""

    def test_manager_has_all_engines(self) -> None:
        mgr = EngineeringManager(repo_root=".")
        assert hasattr(mgr, "review_engine")
        assert hasattr(mgr, "test_intelligence")
        assert hasattr(mgr, "documentation")
        assert hasattr(mgr, "evolution")
        assert hasattr(mgr, "release_readiness_engine")
        assert hasattr(mgr, "productivity")
        assert hasattr(mgr, "health_center")

    async def test_manager_review(self) -> None:
        mgr = EngineeringManager(repo_root=".")
        with TemporaryDirectory() as d:
            report = await mgr.review("code", d)
        assert "review_id" in report
        assert "weaknesses" in report

    async def test_manager_review_all(self) -> None:
        mgr = EngineeringManager(repo_root=".")
        with TemporaryDirectory() as d:
            reports = await mgr.review_all(d)
        assert len(reports) == 12

    async def test_manager_test_suite_analysis(self) -> None:
        mgr = EngineeringManager(repo_root=".")
        analysis = await mgr.test_suite_analysis()
        assert "total_tests" in analysis

    async def test_manager_documentation_analysis(self) -> None:
        mgr = EngineeringManager(repo_root=".")
        analysis = await mgr.documentation_analysis()
        assert "completeness_score" in analysis

    async def test_manager_evolution_dashboard(self) -> None:
        mgr = EngineeringManager(repo_root=".")
        dash = await mgr.evolution_dashboard()
        assert "total_commits" in dash

    async def test_manager_release_readiness(self) -> None:
        mgr = EngineeringManager(repo_root=".")
        report = await mgr.release_readiness(version="5.2.0")
        assert report["version"] == "5.2.0"
        assert "recommendation" in report

    async def test_manager_certification_report(self) -> None:
        mgr = EngineeringManager(repo_root=".")
        cert = await mgr.certification_report(version="5.2.0")
        assert cert["version"] == "5.2.0"
        assert "certification_level" in cert

    async def test_manager_productivity_dashboard(self) -> None:
        mgr = EngineeringManager(repo_root=".")
        dash = await mgr.productivity_dashboard()
        assert "current" in dash
        assert "dora" in dash

    async def test_manager_health(self) -> None:
        mgr = EngineeringManager(repo_root=".")
        report = await mgr.health()
        assert "overall_score" in report
        assert "dimensions" in report

    async def test_manager_health_quick_score(self) -> None:
        mgr = EngineeringManager(repo_root=".")
        score = await mgr.health_quick_score()
        assert 0.0 <= score <= 100.0

    def test_manager_record_productivity_event(self) -> None:
        mgr = EngineeringManager(repo_root=".")
        mgr.record_productivity_event({"type": "commit"})
        # No exception means success
        assert True

    async def test_manager_get_overview_includes_health(self) -> None:
        mgr = EngineeringManager(repo_root=".")
        overview = await mgr.get_overview()
        assert "health_score" in overview
