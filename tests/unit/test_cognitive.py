"""Tests for the Enterprise Cognitive Intelligence Platform (v5.0)."""

from __future__ import annotations

from pathlib import Path

import pytest

from services.cognitive import (
    CognitiveExperience,
    CognitiveManager,
    EnterpriseReportType,
    GraphNode,
    RecommendationStatus,
)


def _make_experience(
    *,
    agents: list[str] | None = None,
    providers: list[str] | None = None,
    success: bool = True,
    cost: float = 0.05,
    latency: float = 1.0,
) -> CognitiveExperience:
    return CognitiveExperience(
        selected_agents=agents or ["agent-a"],
        selected_providers=providers or ["openai"],
        success=success,
        cost_usd=cost,
        latency_s=latency,
        risk_score=0.3,
        confidence_score=0.8,
        tags=["test"],
    )


@pytest.mark.offline
class TestCognitiveExperience:
    """CognitiveExperienceEngine tests."""

    async def test_record_and_stats(self) -> None:
        mgr = CognitiveManager()
        for i in range(10):
            await mgr.record_experience(_make_experience(success=i % 3 != 0))
        stats = await mgr.experience_stats()
        assert stats["total"] == 10
        # i%3==0 → failure for i=0,3,6,9 = 4 failures, 6 successes
        assert stats["successes"] == 6
        assert stats["failures"] == 4
        assert stats["success_rate"] == 0.6

    async def test_timeline(self) -> None:
        mgr = CognitiveManager()
        for _ in range(5):
            await mgr.record_experience(_make_experience())
        timeline = await mgr.experience_timeline(limit=10)
        assert len(timeline) == 5

    async def test_search_by_agent(self) -> None:
        mgr = CognitiveManager()
        await mgr.record_experience(_make_experience(agents=["agent-a"]))
        await mgr.record_experience(_make_experience(agents=["agent-b"]))
        results = await mgr.search_experiences(agent="agent-a")
        assert len(results) == 1

    async def test_export_json(self) -> None:
        mgr = CognitiveManager()
        await mgr.record_experience(_make_experience())
        exported = await mgr.experience_export("json")
        assert "experience_id" in exported

    async def test_export_csv(self) -> None:
        mgr = CognitiveManager()
        await mgr.record_experience(_make_experience())
        exported = await mgr.experience_export("csv")
        assert "experience_id" in exported

    async def test_replay(self) -> None:
        mgr = CognitiveManager()
        exp = _make_experience()
        await mgr.record_experience(exp)
        replay = await mgr.experience_replay(exp.experience_id)
        assert "original" in replay
        assert "replay_inputs" in replay


@pytest.mark.offline
class TestLearningEngine:
    """CognitiveLearningEngine tests."""

    async def test_learn_all(self) -> None:
        mgr = CognitiveManager()
        for i in range(10):
            await mgr.record_experience(
                _make_experience(
                    agents=[f"agent-{i % 2}"],
                    providers=[f"provider-{i % 2}"],
                    success=i % 3 != 0,
                )
            )
        insights = await mgr.learn()
        assert len(insights) > 0
        for insight in insights:
            assert "finding" in insight
            assert "explanation" in insight
            assert "evidence" in insight

    async def test_learning_metrics(self) -> None:
        mgr = CognitiveManager()
        for _ in range(5):
            await mgr.record_experience(_make_experience())
        metrics = await mgr.learning_metrics()
        assert len(metrics) > 0
        assert any(m["name"] == "total_experiences" for m in metrics)

    async def test_best_provider_insight(self) -> None:
        mgr = CognitiveManager()
        for _ in range(5):
            await mgr.record_experience(_make_experience(providers=["openai"], success=True))
        for _ in range(5):
            await mgr.record_experience(_make_experience(providers=["anthropic"], success=False))
        insights = await mgr.learn()
        provider_insights = [i for i in insights if i["category"] == "best_provider"]
        assert len(provider_insights) >= 2
        # OpenAI should rank higher
        assert (
            provider_insights[0]["evidence"]["success_rate"]
            > provider_insights[1]["evidence"]["success_rate"]
        )


@pytest.mark.offline
class TestPredictionEngine:
    """CognitivePredictionEngine tests."""

    async def test_predict_all(self) -> None:
        mgr = CognitiveManager()
        for _ in range(10):
            await mgr.record_experience(_make_experience(success=True))
        predictions = await mgr.predict({"goal": "test", "agent": "agent-a"})
        assert len(predictions) >= 5
        for p in predictions:
            assert "predicted_value" in p
            assert "explanation" in p
            assert "confidence" in p

    async def test_predict_no_data(self) -> None:
        mgr = CognitiveManager()
        predictions = await mgr.predict({})
        assert len(predictions) >= 5
        # Should use defaults with low confidence
        for p in predictions:
            assert p["confidence"] < 0.5

    async def test_predictions_are_explainable(self) -> None:
        mgr = CognitiveManager()
        for _ in range(20):
            await mgr.record_experience(_make_experience())
        predictions = await mgr.predict({"agent": "agent-a"})
        for p in predictions:
            assert len(p["explanation"]) > 10
            assert "evidence" in p


@pytest.mark.offline
class TestOptimizationEngine:
    """CognitiveOptimizationEngine tests."""

    async def test_optimize_with_data(self) -> None:
        mgr = CognitiveManager()
        for _ in range(10):
            await mgr.record_experience(_make_experience(providers=["good"], success=True))
        for _ in range(10):
            await mgr.record_experience(_make_experience(providers=["bad"], success=False))
        recs = await mgr.optimize()
        assert len(recs) >= 1
        for r in recs:
            assert r["requires_approval"] is True
            assert r["status"] == RecommendationStatus.PENDING.value

    async def test_no_recommendations_without_data(self) -> None:
        mgr = CognitiveManager()
        recs = await mgr.optimize()
        assert len(recs) == 0

    async def test_recommendations_never_auto_apply(self) -> None:
        mgr = CognitiveManager()
        for _ in range(20):
            await mgr.record_experience(_make_experience())
        recs = await mgr.optimize()
        for r in recs:
            assert r["requires_approval"] is True
            assert r["status"] == "pending"


@pytest.mark.offline
class TestKnowledgeGraph:
    """EnterpriseKnowledgeGraph tests."""

    def test_add_and_get_node(self) -> None:
        mgr = CognitiveManager()
        node = GraphNode(node_type="agent", name="test-agent", properties={"reliability": 0.9})
        mgr.add_graph_node(node)
        snapshot = mgr.graph_snapshot()
        assert snapshot["node_count"] >= 1

    def test_graph_search(self) -> None:
        mgr = CognitiveManager()
        mgr.add_graph_node(GraphNode(node_type="agent", name="python-coder"))
        mgr.add_graph_node(GraphNode(node_type="provider", name="openai"))
        results = mgr.graph_search("python")
        assert len(results) >= 1
        assert results[0]["name"] == "python-coder"

    def test_impact_analysis(self) -> None:
        mgr = CognitiveManager()
        mgr.add_graph_node(GraphNode(node_type="agent", name="agent-a"))
        snapshot = mgr.graph_snapshot()
        assert snapshot["node_count"] >= 1


@pytest.mark.offline
class TestArchitectureIntelligence:
    """ArchitectureIntelligence tests."""

    async def test_analyze_all(self) -> None:
        mgr = CognitiveManager(repo_root=Path())
        issues = await mgr.arch_analyze()
        assert isinstance(issues, list)
        for issue in issues:
            assert "issue_type" in issue
            assert "severity" in issue
            assert "description" in issue


@pytest.mark.offline
class TestRepositoryIntelligence:
    """RepositoryIntelligence tests."""

    async def test_health_report(self) -> None:
        mgr = CognitiveManager(repo_root=Path())
        health = await mgr.repo_health()
        assert health["has_readme"] is True
        assert health["has_license"] is True
        assert health["source_files"] > 0
        assert health["health_score"] > 50


@pytest.mark.offline
class TestEnterpriseReporting:
    """EnterpriseReporting tests."""

    async def test_generate_execution_report(self) -> None:
        mgr = CognitiveManager()
        for _ in range(5):
            await mgr.record_experience(_make_experience())
        report = await mgr.generate_report(EnterpriseReportType.EXECUTION.value)
        assert report["title"] is not None
        assert len(report["key_findings"]) > 0

    async def test_export_markdown(self) -> None:
        mgr = CognitiveManager()
        await mgr.record_experience(_make_experience())
        md = await mgr.export_report("execution", "markdown")
        assert "#" in md

    async def test_export_csv(self) -> None:
        mgr = CognitiveManager()
        await mgr.record_experience(_make_experience())
        csv = await mgr.export_report("execution", "csv")
        assert "metric" in csv


@pytest.mark.offline
class TestCognitiveManager:
    """CognitiveManager integration tests."""

    async def test_get_all(self) -> None:
        mgr = CognitiveManager()
        for _ in range(5):
            await mgr.record_experience(_make_experience())
        data = await mgr.get_all()
        assert "experience_stats" in data
        assert "learning_insights" in data
        assert "predictions" in data
        assert "recommendations" in data
        assert "knowledge_graph" in data
        assert "architecture_issues" in data
        assert "repository_health" in data


@pytest.mark.offline
class TestCognitiveStress:
    """Stress tests."""

    async def test_100_experiences(self) -> None:
        mgr = CognitiveManager()
        for i in range(100):
            await mgr.record_experience(
                _make_experience(
                    agents=[f"agent-{i % 5}"],
                    providers=[f"provider-{i % 3}"],
                    success=i % 4 != 0,
                    cost=0.01 * i,
                )
            )
        stats = await mgr.experience_stats()
        assert stats["total"] == 100
        insights = await mgr.learn()
        assert len(insights) > 0
        predictions = await mgr.predict({})
        assert len(predictions) >= 5
