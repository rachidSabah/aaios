"""Tests for Knowledge Intelligence, Learning, Repository Intelligence (v5.1 Part 2)."""

from __future__ import annotations

from pathlib import Path

import pytest

from services.knowledge import (
    AutonomousLearningEngine,
    DocumentIntelligence,
    KnowledgeEntry,
    KnowledgeIntelligenceEngine,
    KnowledgePlatform,
    QualityAssurance,
    RecommendationEngine,
    RepositoryIntelligenceEngine,
)


@pytest.mark.offline
class TestKnowledgeIntelligence:
    """KnowledgeIntelligenceEngine tests."""

    async def test_detect_gaps_empty(self) -> None:
        engine = KnowledgeIntelligenceEngine()
        insights = await engine.detect_gaps()
        assert len(insights) >= 1
        assert "empty" in insights[0].finding.lower()

    async def test_detect_gaps_with_entries(self) -> None:
        engine = KnowledgeIntelligenceEngine()
        entries = [
            KnowledgeEntry(title="A", content="content a"),
            KnowledgeEntry(title="B", content="content b", summary="summary", labels=["tag"]),
        ]
        await engine.ingest_entries(entries)
        insights = await engine.detect_gaps()
        assert any("summary" in i.finding.lower() or "label" in i.finding.lower() for i in insights)

    async def test_detect_conflicts(self) -> None:
        engine = KnowledgeIntelligenceEngine()
        entries = [
            KnowledgeEntry(title="Same", content="version A"),
            KnowledgeEntry(title="Same", content="version B"),
        ]
        await engine.ingest_entries(entries)
        insights = await engine.detect_conflicts()
        assert len(insights) >= 1

    async def test_quality_report(self) -> None:
        engine = KnowledgeIntelligenceEngine()
        entries = [KnowledgeEntry(title="Test", content="content", summary="summary", labels=["tag"])]
        await engine.ingest_entries(entries)
        report = await engine.quality_report()
        assert report.total_entries == 1
        assert report.avg_quality > 0

    async def test_analyze_all(self) -> None:
        engine = KnowledgeIntelligenceEngine()
        entries = [KnowledgeEntry(title="Test", content="content", summary="summary", labels=["tag"])]
        await engine.ingest_entries(entries)
        insights = await engine.analyze_all()
        assert isinstance(insights, list)


@pytest.mark.offline
class TestAutonomousLearning:
    """AutonomousLearningEngine tests."""

    async def test_learn_from_success(self) -> None:
        engine = AutonomousLearningEngine()
        lesson = await engine.learn_from_execution(
            goal="test goal", success=True, agent_id="agent-a", provider="openai",
            duration_s=1.0, cost_usd=0.05,
        )
        assert lesson.category == "best_practice"
        assert "test goal" in lesson.title

    async def test_learn_from_failure(self) -> None:
        engine = AutonomousLearningEngine()
        lesson = await engine.learn_from_execution(
            goal="failing goal", success=False, agent_id="agent-b",
            error="timeout", retries=3,
        )
        assert lesson.category == "anti_pattern"
        assert "failing goal" in lesson.title

    async def test_learn_from_approval(self) -> None:
        engine = AutonomousLearningEngine()
        lesson = await engine.learn_from_approval(
            action="delete_file", approved=False, risk_level="high", reason="too risky",
        )
        assert lesson.category == "anti_pattern"

    async def test_learn_from_feedback(self) -> None:
        engine = AutonomousLearningEngine()
        lesson = await engine.learn_from_feedback(
            target="execution", feedback="great work", rating=5,
        )
        assert lesson.category == "best_practice"

    async def test_generate_playbook(self) -> None:
        engine = AutonomousLearningEngine()
        await engine.learn_from_execution(goal="deploy", success=False, error="timeout")
        pb = await engine.generate_playbook(
            title="Deployment Recovery",
            description="Steps to recover from deployment failures",
            trigger_conditions=["deploy", "timeout"],
            steps=[{"step": 1, "action": "check logs"}],
        )
        assert pb.title == "Deployment Recovery"
        assert len(pb.steps) == 1

    async def test_get_lessons(self) -> None:
        engine = AutonomousLearningEngine()
        for i in range(5):
            await engine.learn_from_execution(goal=f"goal {i}", success=i % 2 == 0)
        lessons = await engine.get_lessons(limit=10)
        assert len(lessons) == 5

    async def test_merge_duplicates(self) -> None:
        engine = AutonomousLearningEngine()
        await engine.learn_from_execution(goal="same", success=True, agent_id="a")
        await engine.learn_from_execution(goal="same", success=True, agent_id="a")
        merged = await engine.merge_duplicates()
        assert merged >= 1

    async def test_stats(self) -> None:
        engine = AutonomousLearningEngine()
        for _ in range(3):
            await engine.learn_from_execution(goal="test", success=True)
        stats = await engine.stats()
        assert stats["total_lessons"] == 3


@pytest.mark.offline
class TestRecommendationEngine:
    """RecommendationEngine tests."""

    async def test_recommend_documents(self) -> None:
        learning = AutonomousLearningEngine()
        rec = RecommendationEngine(learning)
        entries = [KnowledgeEntry(title="Python Guide", content="Python is great", labels=["python"])]
        await rec.ingest(entries, [])
        results = await rec.recommend_documents("python")
        assert len(results) >= 1

    async def test_recommend_lessons(self) -> None:
        learning = AutonomousLearningEngine()
        await learning.learn_from_execution(goal="python deployment", success=True)
        rec = RecommendationEngine(learning)
        await rec.ingest([], [])
        results = await rec.recommend_lessons("python")
        assert len(results) >= 1

    async def test_recommend_all(self) -> None:
        learning = AutonomousLearningEngine()
        await learning.learn_from_execution(goal="deploy", success=True)
        rec = RecommendationEngine(learning)
        entries = [KnowledgeEntry(title="Deploy Guide", content="how to deploy", labels=["deploy"])]
        await rec.ingest(entries, [])
        recs = await rec.recommend_all("deploy")
        assert len(recs) >= 1


@pytest.mark.offline
class TestRepositoryIntelligence:
    """RepositoryIntelligenceEngine tests."""

    async def test_analyze(self) -> None:
        engine = RepositoryIntelligenceEngine(Path())
        analysis = await engine.analyze()
        assert analysis.total_files > 0
        assert analysis.total_lines > 0
        assert analysis.health_score >= 0


@pytest.mark.offline
class TestDocumentIntelligence:
    """DocumentIntelligence tests."""

    async def test_analyze_markdown(self) -> None:
        engine = DocumentIntelligence()
        result = await engine.analyze("test.md", "# Title\nSome [link](http://example.com) text")
        assert "Markdown" in result.summary
        assert len(result.references) >= 1

    async def test_analyze_python(self) -> None:
        engine = DocumentIntelligence()
        result = await engine.analyze("test.py", "class Foo:\n    pass\ndef bar():\n    pass")
        assert "Foo" in result.entities
        assert "bar" in result.entities

    async def test_analyze_json(self) -> None:
        engine = DocumentIntelligence()
        result = await engine.analyze("test.json", '{"key1": "val1", "key2": "val2"}')
        assert "key1" in result.entities

    async def test_analyze_csv(self) -> None:
        engine = DocumentIntelligence()
        result = await engine.analyze("test.csv", "name,age\nAlice,30\nBob,25")
        assert len(result.tables) >= 1


@pytest.mark.offline
class TestQualityAssurance:
    """QualityAssurance tests."""

    async def test_validate(self) -> None:
        qa = QualityAssurance()
        entries = [
            KnowledgeEntry(title="A", content="content a"),
            KnowledgeEntry(title="B", content="content b", summary="summary", labels=["tag"]),
        ]
        issues = await qa.validate(entries)
        assert len(issues) > 0  # Entry A should have issues

    async def test_repair_suggestions(self) -> None:
        qa = QualityAssurance()
        entries = [KnowledgeEntry(title="A", content="content a")]
        issues = await qa.validate(entries)
        suggestions = await qa.repair_suggestions(issues)
        assert len(suggestions) == len(issues)


@pytest.mark.offline
class TestKnowledgeIntegration:
    """Integration tests for the full knowledge platform."""

    async def test_full_lifecycle(self) -> None:
        platform = KnowledgePlatform()
        # Create knowledge
        entry = KnowledgeEntry(title="Integration Test", content="test content", summary="summary", labels=["test"])
        await platform.create_entry(entry)
        # Learn
        learning = AutonomousLearningEngine()
        await learning.learn_from_execution(goal="integration test", success=True)
        # Recommend
        rec = RecommendationEngine(learning)
        await rec.ingest([entry], [])
        recs = await rec.recommend_all("integration")
        assert len(recs) >= 1
        # Quality
        ki = KnowledgeIntelligenceEngine()
        await ki.ingest_entries([entry])
        report = await ki.quality_report()
        assert report.total_entries == 1
