"""Comprehensive tests for the Experience & Learning Engine."""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4

import pytest

from core.contracts.actor import ActorRef, ActorType
from core.contracts.event import Event
from core.event_bus import InMemoryEventBus
from services.experience import (
    ExperienceAnalyzer,
    ExperienceCollector,
    ExperienceCompressor,
    ExperienceExporter,
    ExperienceFilter,
    ExperienceIndexer,
    ExperienceNotFoundError,
    ExperienceOutcome,
    ExperienceRecord,
    ExperienceReplayer,
    ExperienceRetentionManager,
    ExperienceRetriever,
    ExperienceScorer,
    ExperienceStore,
    LearningEngine,
    ReplayMode,
    RetentionPolicy,
    SearchType,
    TokenUsage,
    UserFeedback,
)


def _make_record(
    *,
    agent_id: str = "test-agent",
    agent_type: str = "coding",
    goal: str = "test goal",
    success: bool = True,
    outcome: str | None = None,
    provider: str | None = "openai",
    model: str | None = "gpt-4o",
    capabilities: list[str] | None = None,
    reflection_score: float = 0.8,
    qa_score: float = 0.85,
    cost_usd: float = 0.05,
    latency_s: float = 1.0,
    failure_reason: str | None = None,
    recovery_action: str | None = None,
    workflow_id: str | None = None,
    input_summary: str = "test input",
    output_summary: str = "test output",
) -> ExperienceRecord:
    return ExperienceRecord(
        task_id=uuid4(),
        agent_id=agent_id,
        agent_type=agent_type,
        provider=provider,
        model=model,
        capabilities_used=capabilities or ["code.generate"],
        goal=goal,
        input_summary=input_summary,
        output_summary=output_summary,
        outcome=outcome or (ExperienceOutcome.SUCCESS.value if success else ExperienceOutcome.FAILURE.value),
        success=success,
        failure_reason=failure_reason,
        recovery_action=recovery_action,
        execution_time_s=latency_s,
        latency_s=latency_s,
        cost_usd=cost_usd,
        reflection_score=reflection_score,
        qa_score=qa_score,
        confidence=0.8,
        workflow_id=workflow_id,
    )


def _make_event(
    topic: str,
    payload: dict | None = None,
    correlation_id: UUID | None = None,
) -> Event:
    return Event(
        topic=topic,
        correlation_id=correlation_id or uuid4(),
        actor=ActorRef(type=ActorType.SYSTEM, id="test"),
        payload=payload or {},
    )


# ============================================================
# Models
# ============================================================


@pytest.mark.offline
class TestExperienceRecord:
    """ExperienceRecord dataclass tests."""

    def test_creation_minimal(self) -> None:
        r = _make_record()
        assert r.agent_id == "test-agent"
        assert r.success is True
        assert r.context_hash  # auto-computed

    def test_creation_with_all_fields(self) -> None:
        r = ExperienceRecord(
            task_id=uuid4(),
            agent_id="full-agent",
            agent_type="coding",
            provider="anthropic",
            model="claude-3-5-sonnet",
            capabilities_used=["code.generate", "code.review"],
            goal="full goal",
            input_summary="full input",
            output_summary="full output",
            outcome=ExperienceOutcome.SUCCESS.value,
            success=True,
            execution_time_s=2.5,
            latency_s=2.3,
            retries=1,
            reflection_score=0.9,
            qa_score=0.85,
            user_feedback=UserFeedback(rating=5, comment="great", approved=True),
            cost_usd=0.15,
            token_usage=TokenUsage(input_tokens=100, output_tokens=50),
            confidence=0.9,
            workflow_id="wf-1",
        )
        assert r.provider == "anthropic"
        assert r.token_usage.total_tokens == 150
        assert r.user_feedback.rating == 5

    def test_immutable(self) -> None:
        r = _make_record()
        with pytest.raises(AttributeError):
            r.agent_id = "other"  # type: ignore[misc]

    def test_to_dict_and_from_dict_roundtrip(self) -> None:
        r = _make_record(goal="roundtrip test", capabilities=["code.generate", "code.review"])
        d = r.to_dict()
        assert d["goal"] == "roundtrip test"
        assert d["capabilities_used"] == ["code.generate", "code.review"]
        restored = ExperienceRecord.from_dict(d)
        assert restored.goal == r.goal
        assert restored.agent_id == r.agent_id
        assert restored.capabilities_used == r.capabilities_used
        assert restored.experience_id == r.experience_id

    def test_context_hash_deterministic(self) -> None:
        r1 = _make_record(agent_id="a", goal="g", input_summary="i")
        r2 = _make_record(agent_id="a", goal="g", input_summary="i")
        assert r1.context_hash == r2.context_hash

    def test_context_hash_differs_for_different_inputs(self) -> None:
        r1 = _make_record(agent_id="a", goal="g1", input_summary="i")
        r2 = _make_record(agent_id="a", goal="g2", input_summary="i")
        assert r1.context_hash != r2.context_hash

    def test_quality_score_with_feedback(self) -> None:
        r = ExperienceRecord(
            task_id=uuid4(),
            agent_id="a",
            agent_type="coding",
            reflection_score=0.8,
            qa_score=0.8,
            user_feedback=UserFeedback(rating=5),
        )
        # 0.8*0.3 + 0.8*0.4 + 1.0*0.3 = 0.24 + 0.32 + 0.30 = 0.86
        assert r.quality_score() == pytest.approx(0.86, abs=0.01)

    def test_quality_score_without_feedback(self) -> None:
        r = _make_record(reflection_score=0.8, qa_score=0.8)
        # No feedback: 0.8*0.4286 + 0.8*0.5714 = ~0.8
        assert r.quality_score() == pytest.approx(0.8, abs=0.01)


# ============================================================
# Store
# ============================================================


@pytest.mark.offline
class TestExperienceStore:
    """ExperienceStore tests."""

    async def test_store_and_get(self) -> None:
        store = ExperienceStore()
        r = _make_record()
        await store.store(r)
        fetched = await store.get(r.experience_id)
        assert fetched.experience_id == r.experience_id
        assert fetched.agent_id == r.agent_id

    async def test_get_not_found(self) -> None:
        store = ExperienceStore()
        with pytest.raises(ExperienceNotFoundError):
            await store.get(uuid4())

    async def test_query_all(self) -> None:
        store = ExperienceStore()
        for i in range(5):
            await store.store(_make_record(agent_id=f"agent-{i}"))
        records = await store.query()
        assert len(records) == 5

    async def test_query_with_filter(self) -> None:
        store = ExperienceStore()
        await store.store(_make_record(agent_id="a1", success=True))
        await store.store(_make_record(agent_id="a2", success=False))
        records = await store.query(ExperienceFilter(agent_id="a1"))
        assert len(records) == 1
        assert records[0].agent_id == "a1"

    async def test_query_filter_by_success(self) -> None:
        store = ExperienceStore()
        await store.store(_make_record(success=True))
        await store.store(_make_record(success=False))
        successes = await store.query(ExperienceFilter(success=True))
        failures = await store.query(ExperienceFilter(success=False))
        assert len(successes) == 1
        assert len(failures) == 1

    async def test_query_filter_by_capability(self) -> None:
        store = ExperienceStore()
        await store.store(_make_record(capabilities=["code.generate"]))
        await store.store(_make_record(capabilities=["code.review"]))
        records = await store.query(ExperienceFilter(capability="code.generate"))
        assert len(records) == 1

    async def test_query_pagination(self) -> None:
        store = ExperienceStore()
        for i in range(10):
            await store.store(_make_record(agent_id=f"agent-{i}"))
        page1 = await store.query(limit=5, offset=0)
        page2 = await store.query(limit=5, offset=5)
        assert len(page1) == 5
        assert len(page2) == 5
        page1_ids = {r.experience_id for r in page1}
        page2_ids = {r.experience_id for r in page2}
        assert page1_ids.isdisjoint(page2_ids)

    async def test_count(self) -> None:
        store = ExperienceStore()
        for _ in range(5):
            await store.store(_make_record())
        assert await store.count() == 5
        assert await store.count(ExperienceFilter(success=True)) == 5
        assert await store.count(ExperienceFilter(success=False)) == 0

    async def test_summarize(self) -> None:
        store = ExperienceStore()
        for i in range(10):
            await store.store(_make_record(
                success=i % 3 != 0,
                cost_usd=0.01 * i,
                latency_s=0.5 * i,
            ))
        summary = await store.summarize()
        assert summary.total_count == 10
        # i%3==0 → failure (i=0,3,6,9) = 4 failures, 6 successes
        assert summary.success_count == 6
        assert summary.failure_count == 4
        assert summary.success_rate == 0.6

    async def test_find_by_context_hash(self) -> None:
        store = ExperienceStore()
        r1 = _make_record(agent_id="a", goal="g", input_summary="i")
        r2 = _make_record(agent_id="a", goal="g", input_summary="i")
        r3 = _make_record(agent_id="a", goal="other", input_summary="i")
        await store.store(r1)
        await store.store(r2)
        await store.store(r3)
        matches = await store.find_by_context_hash(r1.context_hash)
        assert len(matches) == 2

    async def test_list_agents_providers_capabilities(self) -> None:
        store = ExperienceStore()
        await store.store(_make_record(agent_id="a1", provider="openai", capabilities=["code.generate"]))
        await store.store(_make_record(agent_id="a2", provider="anthropic", capabilities=["code.review"]))
        agents = await store.list_agents()
        providers = await store.list_providers()
        capabilities = await store.list_capabilities()
        assert set(agents) == {"a1", "a2"}
        assert set(providers) == {"openai", "anthropic"}
        assert set(capabilities) == {"code.generate", "code.review"}

    async def test_delete(self) -> None:
        store = ExperienceStore()
        r = _make_record()
        await store.store(r)
        assert await store.delete(r.experience_id) is True
        assert await store.delete(r.experience_id) is False
        with pytest.raises(ExperienceNotFoundError):
            await store.get(r.experience_id)

    async def test_persistence_to_disk(self, tmp_path: Path) -> None:
        store1 = ExperienceStore(storage_dir=tmp_path)
        r = await store1.store(_make_record(goal="persistent"))
        # New store loading from same dir should find it
        store2 = ExperienceStore(storage_dir=tmp_path)
        fetched = await store2.get(r.experience_id)
        assert fetched.goal == "persistent"

    async def test_delete_older_than(self) -> None:
        store = ExperienceStore()
        old_record = ExperienceRecord(
            task_id=uuid4(), agent_id="old", agent_type="coding",
            timestamp=datetime.now(UTC) - timedelta(days=100),
        )
        new_record = _make_record(agent_id="new")
        await store.store(old_record)
        await store.store(new_record)
        cutoff = datetime.now(UTC) - timedelta(days=50)
        deleted = await store.delete_older_than(cutoff)
        assert deleted == 1
        assert await store.count() == 1


# ============================================================
# Collector
# ============================================================


@pytest.mark.offline
class TestExperienceCollector:
    """ExperienceCollector tests."""

    async def test_subscribe_and_handle_task_completed(self) -> None:
        store = ExperienceStore()
        collector = ExperienceCollector(store)
        bus = InMemoryEventBus()
        await collector.subscribe(bus)

        task_id = uuid4()
        # Publish task lifecycle events
        await bus.publish(_make_event(
            "task.submitted",
            {"task_id": str(task_id), "goal": "test goal", "input_summary": "test input"},
            correlation_id=task_id,
        ))
        await bus.publish(_make_event(
            "agent.dispatched",
            {"task_id": str(task_id), "agent_id": "test-agent", "agent_type": "coding",
             "provider": "openai", "model": "gpt-4o", "capability": "code.generate"},
        ))
        await bus.publish(_make_event(
            "agent.completed",
            {"task_id": str(task_id), "output_summary": "test output", "cost_usd": 0.05,
             "input_tokens": 100, "output_tokens": 50, "success": True, "confidence": 0.8},
        ))
        await bus.publish(_make_event(
            "task.completed",
            {"task_id": str(task_id), "outcome": "success", "success": True,
             "reflection_score": 0.9, "qa_score": 0.85, "cost_usd": 0.05},
        ))
        await asyncio.sleep(0.1)

        records = await store.query()
        assert len(records) == 1
        r = records[0]
        assert r.agent_id == "test-agent"
        assert r.goal == "test goal"
        assert r.success is True
        assert r.reflection_score == 0.9
        assert r.qa_score == 0.85
        # Cost is accumulated from both agent.completed (0.05) and task.completed (0.05)
        assert r.cost_usd == 0.10
        assert r.token_usage.input_tokens == 100

    async def test_collector_handles_failure(self) -> None:
        store = ExperienceStore()
        collector = ExperienceCollector(store)
        bus = InMemoryEventBus()
        await collector.subscribe(bus)

        task_id = uuid4()
        await bus.publish(_make_event(
            "task.submitted",
            {"task_id": str(task_id), "goal": "failing task"},
        ))
        await bus.publish(_make_event(
            "agent.dispatched",
            {"task_id": str(task_id), "agent_id": "fail-agent", "agent_type": "coding",
             "provider": "openai", "capability": "code.generate"},
        ))
        await bus.publish(_make_event(
            "agent.completed",
            {"task_id": str(task_id), "success": False, "error": "timeout"},
        ))
        await bus.publish(_make_event(
            "task.completed",
            {"task_id": str(task_id), "outcome": "failure", "success": False,
             "failure_reason": "timeout", "recovery_action": "retry"},
        ))
        await asyncio.sleep(0.1)

        records = await store.query()
        assert len(records) == 1
        r = records[0]
        assert r.success is False
        assert r.failure_reason == "timeout"
        assert r.recovery_action == "retry"

    async def test_manual_record(self) -> None:
        store = ExperienceStore()
        collector = ExperienceCollector(store)
        r = _make_record()
        stored = await collector.record_manual(r)
        assert stored.experience_id == r.experience_id
        assert await store.count() == 1

    async def test_in_flight_count(self) -> None:
        store = ExperienceStore()
        collector = ExperienceCollector(store)
        bus = InMemoryEventBus()
        await collector.subscribe(bus)
        task_id = uuid4()
        await bus.publish(_make_event(
            "task.submitted",
            {"task_id": str(task_id), "goal": "in flight"},
        ))
        await asyncio.sleep(0.05)
        assert await collector.in_flight_count() == 1


# ============================================================
# Indexer + Retriever
# ============================================================


@pytest.mark.offline
class TestExperienceIndexer:
    """ExperienceIndexer tests."""

    async def test_rebuild_and_search(self) -> None:
        store = ExperienceStore()
        for i in range(10):
            await store.store(_make_record(
                goal=f"generate python function {i}",
                input_summary="sort a list of numbers",
            ))
        indexer = ExperienceIndexer(store)
        count = await indexer.rebuild()
        assert count == 10
        results = await indexer.search("python function")
        assert len(results) > 0
        assert all(hasattr(r, "score") for r in results)

    async def test_search_no_results(self) -> None:
        store = ExperienceStore()
        await store.store(_make_record(goal="generate python"))
        indexer = ExperienceIndexer(store)
        await indexer.rebuild()
        results = await indexer.search("cooking recipe")
        assert len(results) == 0

    async def test_search_ranks_by_relevance(self) -> None:
        store = ExperienceStore()
        await store.store(_make_record(goal="python debugging"))
        await store.store(_make_record(goal="python web development"))
        await store.store(_make_record(goal="cooking italian food"))
        indexer = ExperienceIndexer(store)
        await indexer.rebuild()
        results = await indexer.search("python debugging")
        if results:
            top = results[0]
            assert "python" in top.experience.goal.lower()


@pytest.mark.offline
class TestExperienceRetriever:
    """ExperienceRetriever tests."""

    async def test_similar_successes(self) -> None:
        store = ExperienceStore()
        for i in range(5):
            await store.store(_make_record(
                goal=f"python function {i}", success=True,
            ))
        await store.store(_make_record(goal="python failure", success=False))
        indexer = ExperienceIndexer(store)
        retriever = ExperienceRetriever(store, indexer)
        results = await retriever.similar_successes("python")
        assert all(r.experience.success for r in results)

    async def test_similar_failures(self) -> None:
        store = ExperienceStore()
        await store.store(_make_record(goal="python success", success=True))
        for i in range(3):
            await store.store(_make_record(
                goal=f"python failure {i}", success=False,
            ))
        indexer = ExperienceIndexer(store)
        retriever = ExperienceRetriever(store, indexer)
        results = await retriever.similar_failures("python")
        assert all(not r.experience.success for r in results)

    async def test_best_agent_for_capability(self) -> None:
        store = ExperienceStore()
        # Agent A: 5 successes
        for _ in range(5):
            await store.store(_make_record(agent_id="agent-a", success=True, capabilities=["code.generate"]))
        # Agent B: 5 failures
        for _ in range(5):
            await store.store(_make_record(agent_id="agent-b", success=False, capabilities=["code.generate"]))
        indexer = ExperienceIndexer(store)
        retriever = ExperienceRetriever(store, indexer)
        results = await retriever.best_agent_for_capability("code.generate")
        assert len(results) >= 1
        # Agent A should rank higher
        assert results[0]["agent_id"] == "agent-a"

    async def test_fastest_provider(self) -> None:
        store = ExperienceStore()
        for _ in range(3):
            await store.store(_make_record(provider="fast", latency_s=0.5))
        for _ in range(3):
            await store.store(_make_record(provider="slow", latency_s=5.0))
        indexer = ExperienceIndexer(store)
        retriever = ExperienceRetriever(store, indexer)
        results = await retriever.fastest_provider()
        assert len(results) >= 1
        assert results[0]["provider"] == "fast"

    async def test_cheapest_provider(self) -> None:
        store = ExperienceStore()
        for _ in range(3):
            await store.store(_make_record(provider="cheap", cost_usd=0.01))
        for _ in range(3):
            await store.store(_make_record(provider="expensive", cost_usd=1.0))
        indexer = ExperienceIndexer(store)
        retriever = ExperienceRetriever(store, indexer)
        results = await retriever.cheapest_provider()
        assert len(results) >= 1
        assert results[0]["provider"] == "cheap"

    async def test_highest_quality_workflows(self) -> None:
        store = ExperienceStore()
        for _ in range(3):
            await store.store(_make_record(
                workflow_id="wf-good", reflection_score=0.9, qa_score=0.9,
            ))
        for _ in range(3):
            await store.store(_make_record(
                workflow_id="wf-bad", reflection_score=0.3, qa_score=0.3,
            ))
        indexer = ExperienceIndexer(store)
        retriever = ExperienceRetriever(store, indexer)
        results = await retriever.highest_quality_workflows()
        assert len(results) >= 1
        assert results[0]["workflow_id"] == "wf-good"

    async def test_search_with_type(self) -> None:
        store = ExperienceStore()
        for _ in range(5):
            await store.store(_make_record(provider="openai", latency_s=1.0))
        indexer = ExperienceIndexer(store)
        retriever = ExperienceRetriever(store, indexer)
        result = await retriever.search("openai", search_type=SearchType.FASTEST_PROVIDER)
        assert result["type"] == SearchType.FASTEST_PROVIDER
        assert len(result["results"]) >= 1


# ============================================================
# Analyzer + Scorer
# ============================================================


@pytest.mark.offline
class TestExperienceAnalyzer:
    """ExperienceAnalyzer tests."""

    async def test_learning_stats_empty(self) -> None:
        store = ExperienceStore()
        analyzer = ExperienceAnalyzer(store)
        stats = await analyzer.learning_stats()
        assert stats.total_experiences == 0

    async def test_learning_stats_populated(self) -> None:
        store = ExperienceStore()
        for i in range(20):
            await store.store(_make_record(
                agent_id=f"agent-{i % 3}",
                provider=f"provider-{i % 2}",
                success=i % 5 != 0,
                cost_usd=0.05 * i,
                capabilities=["code.generate"],
                workflow_id=f"wf-{i % 4}",
            ))
        analyzer = ExperienceAnalyzer(store)
        stats = await analyzer.learning_stats()
        assert stats.total_experiences == 20
        assert stats.agent_count == 3
        assert stats.provider_count == 2
        assert stats.capability_count == 1
        assert stats.workflow_count == 4
        # i%5==0 → failure (i=0,5,10,15) = 4 failures, 16 successes
        assert stats.overall_success_rate == 0.8

    async def test_discover_patterns(self) -> None:
        store = ExperienceStore()
        # 5 successes with agent-a on code.generate
        for _ in range(5):
            await store.store(_make_record(
                agent_id="agent-a", success=True, capabilities=["code.generate"],
            ))
        # 3 failures with same reason
        for _ in range(3):
            await store.store(_make_record(
                agent_id="agent-b", success=False, capabilities=["code.generate"],
                failure_reason="timeout", recovery_action="retry",
            ))
        analyzer = ExperienceAnalyzer(store)
        report = await analyzer.discover_patterns()
        assert len(report.success_patterns) >= 1
        assert any("agent-a" in p.description for p in report.success_patterns)
        assert len(report.failure_patterns) >= 1
        assert any("timeout" in p.failure_reason for p in report.failure_patterns)

    async def test_trend_over_time(self) -> None:
        store = ExperienceStore()
        # Create records with varying timestamps over last 7 days
        for days_ago in range(7):
            r = _make_record(success=days_ago % 2 == 0)
            # Override timestamp by storing then manually replacing
            from dataclasses import replace
            old_ts = datetime.now(UTC) - timedelta(days=days_ago)
            r = replace(r, timestamp=old_ts)
            await store.store(r)
        analyzer = ExperienceAnalyzer(store)
        series = await analyzer.trend_over_time(days=7, bucket="day")
        assert len(series) >= 1
        for point in series:
            assert "success_rate" in point
            assert "count" in point


@pytest.mark.offline
class TestExperienceScorer:
    """ExperienceScorer tests."""

    async def test_score_agent(self) -> None:
        store = ExperienceStore()
        for i in range(10):
            await store.store(_make_record(
                agent_id="agent-a", success=i % 5 != 0,
                reflection_score=0.8, qa_score=0.85,
            ))
        scorer = ExperienceScorer(store)
        reliability = await scorer.score_agent("agent-a")
        assert reliability.agent_id == "agent-a"
        assert reliability.experience_count == 10
        assert reliability.success_rate == 0.8
        assert 0.0 <= reliability.reliability_score <= 1.0

    async def test_score_agent_no_data(self) -> None:
        store = ExperienceStore()
        scorer = ExperienceScorer(store)
        reliability = await scorer.score_agent("unknown")
        assert reliability.experience_count == 0
        assert reliability.reliability_score == 0.0

    async def test_score_provider(self) -> None:
        store = ExperienceStore()
        for _ in range(5):
            await store.store(_make_record(provider="openai", success=True, latency_s=1.0))
        scorer = ExperienceScorer(store)
        reliability = await scorer.score_provider("openai")
        assert reliability.provider == "openai"
        assert reliability.success_rate == 1.0
        assert reliability.reliability_score > 0.5

    async def test_score_capability(self) -> None:
        store = ExperienceStore()
        for i in range(5):
            await store.store(_make_record(
                agent_id="agent-a", success=True, capabilities=["code.generate"],
            ))
        for i in range(3):
            await store.store(_make_record(
                agent_id="agent-b", success=False, capabilities=["code.generate"],
            ))
        scorer = ExperienceScorer(store)
        cap = await scorer.score_capability("code.generate")
        assert cap.capability == "code.generate"
        assert cap.experience_count == 8
        assert cap.best_agent_id == "agent-a"

    async def test_rank_agents(self) -> None:
        store = ExperienceStore()
        for _ in range(5):
            await store.store(_make_record(agent_id="good", success=True, reflection_score=0.9, qa_score=0.9))
        for _ in range(5):
            await store.store(_make_record(agent_id="bad", success=False, reflection_score=0.3, qa_score=0.3))
        scorer = ExperienceScorer(store)
        ranked = await scorer.rank_agents()
        assert ranked[0].agent_id == "good"
        assert ranked[1].agent_id == "bad"

    async def test_recommend_agent_for_capability(self) -> None:
        store = ExperienceStore()
        for _ in range(5):
            await store.store(_make_record(
                agent_id="recommended", success=True, capabilities=["code.generate"],
                reflection_score=0.9, qa_score=0.9, cost_usd=0.01,
            ))
        for _ in range(3):
            await store.store(_make_record(
                agent_id="not-recommended", success=False, capabilities=["code.generate"],
            ))
        scorer = ExperienceScorer(store)
        rec = await scorer.recommend_agent_for_capability("code.generate")
        assert rec is not None
        assert rec["recommended_agent_id"] == "recommended"
        assert rec["success_rate"] == 1.0

    async def test_recommend_returns_none_for_unknown(self) -> None:
        store = ExperienceStore()
        scorer = ExperienceScorer(store)
        rec = await scorer.recommend_agent_for_capability("nonexistent")
        assert rec is None


# ============================================================
# Replayer
# ============================================================


@pytest.mark.offline
class TestExperienceReplayer:
    """ExperienceReplayer tests."""

    async def test_dry_run(self) -> None:
        store = ExperienceStore()
        r = await store.store(_make_record())
        replayer = ExperienceReplayer(store)
        result = await replayer.replay(r.experience_id, mode=ReplayMode.DRY_RUN)
        assert result.error is None
        assert result.comparison is not None
        assert result.comparison["match"] is True

    async def test_replay_not_found(self) -> None:
        store = ExperienceStore()
        replayer = ExperienceReplayer(store)
        result = await replayer.replay(uuid4(), mode=ReplayMode.DRY_RUN)
        assert result.error is not None
        assert "not found" in result.error.lower()

    async def test_re_execute_without_executor(self) -> None:
        store = ExperienceStore()
        r = await store.store(_make_record())
        replayer = ExperienceReplayer(store)
        result = await replayer.replay(r.experience_id, mode=ReplayMode.RE_EXECUTE)
        assert result.error is not None
        assert "executor" in result.error.lower()

    async def test_re_execute_with_executor(self) -> None:
        store = ExperienceStore()
        r = await store.store(_make_record())
        executed = False

        async def executor(**kwargs):
            nonlocal executed
            executed = True
            return _make_record(
                agent_id=kwargs["agent_id"],
                goal=kwargs["goal"],
                success=True,
            )

        replayer = ExperienceReplayer(store, executor=executor)
        result = await replayer.replay(r.experience_id, mode=ReplayMode.RE_EXECUTE)
        assert executed
        assert result.new_experience_id is not None
        assert result.comparison is not None

    async def test_compare_mode(self) -> None:
        store = ExperienceStore()
        r = await store.store(_make_record(agent_id="original"))

        async def executor(**kwargs):
            return _make_record(
                agent_id=kwargs["agent_id"],
                goal=kwargs["goal"],
                success=True,
                reflection_score=0.95,  # higher quality
            )

        replayer = ExperienceReplayer(store, executor=executor)
        result = await replayer.replay(
            r.experience_id, mode=ReplayMode.COMPARE, comparison_agent_id="comparison",
        )
        assert result.comparison is not None
        assert result.comparison["comparison_agent_id"] == "comparison"


# ============================================================
# Exporter + Compressor + Retention
# ============================================================


@pytest.mark.offline
class TestExperienceExporter:
    """ExperienceExporter tests."""

    async def test_export_json(self) -> None:
        store = ExperienceStore()
        for i in range(3):
            await store.store(_make_record(goal=f"goal {i}"))
        exporter = ExperienceExporter(store)
        json_str = await exporter.export_json()
        data = json.loads(json_str)
        assert len(data) == 3
        assert all("experience_id" in r for r in data)

    async def test_export_csv(self) -> None:
        store = ExperienceStore()
        for i in range(3):
            await store.store(_make_record(goal=f"goal {i}"))
        exporter = ExperienceExporter(store)
        csv_str = await exporter.export_csv()
        lines = csv_str.strip().split("\n")
        assert len(lines) == 4  # header + 3 records
        assert "experience_id" in lines[0]

    async def test_export_summary_json(self) -> None:
        store = ExperienceStore()
        for i in range(5):
            await store.store(_make_record(success=i % 2 == 0))
        exporter = ExperienceExporter(store)
        summary_str = await exporter.export_summary_json()
        summary = json.loads(summary_str)
        assert summary["total_count"] == 5


@pytest.mark.offline
class TestExperienceCompressor:
    """ExperienceCompressor tests."""

    async def test_compress_similar(self) -> None:
        store = ExperienceStore()
        # 6 similar records (same agent, goal, capability)
        for _ in range(6):
            await store.store(_make_record(
                agent_id="agent-a", goal="same goal", capabilities=["code.generate"],
            ))
        # 2 different records (below min_group_size)
        for _ in range(2):
            await store.store(_make_record(
                agent_id="agent-b", goal="different goal", capabilities=["code.review"],
            ))
        compressor = ExperienceCompressor(store)
        summaries = await compressor.compress(min_group_size=5)
        assert len(summaries) == 1
        assert summaries[0].experience_count == 6
        assert len(summaries[0].merged_ids) == 5  # 1 kept, 5 merged
        # Store should now have 3 records: 1 representative + 2 different
        assert await store.count() == 3


@pytest.mark.offline
class TestExperienceRetentionManager:
    """ExperienceRetentionManager tests."""

    async def test_enforce_deletes_old(self) -> None:
        store = ExperienceStore()
        # Old record
        old = ExperienceRecord(
            task_id=uuid4(), agent_id="old", agent_type="coding",
            timestamp=datetime.now(UTC) - timedelta(days=200),
        )
        await store.store(old)
        # New record
        await store.store(_make_record(agent_id="new"))
        retention = ExperienceRetentionManager(
            store,
            policy=RetentionPolicy(max_age_days=90, compress_before_delete=False),
        )
        result = await retention.enforce()
        assert result["deleted_old"] == 1
        assert result["remaining_count"] == 1

    async def test_enforce_max_total_records(self) -> None:
        store = ExperienceStore()
        for _ in range(20):
            await store.store(_make_record())
        retention = ExperienceRetentionManager(
            store,
            policy=RetentionPolicy(max_age_days=365, max_total_records=10, compress_before_delete=False),
        )
        result = await retention.enforce()
        assert result["deleted_over_limit"] == 10
        assert result["remaining_count"] == 10


# ============================================================
# LearningEngine facade
# ============================================================


@pytest.mark.offline
class TestLearningEngine:
    """LearningEngine facade tests."""

    async def test_record_and_get(self) -> None:
        engine = LearningEngine()
        r = _make_record()
        stored = await engine.record(r)
        fetched = await engine.get(stored.experience_id)
        assert fetched.experience_id == stored.experience_id

    async def test_search(self) -> None:
        engine = LearningEngine()
        for i in range(5):
            await engine.record(_make_record(goal=f"python function {i}"))
        result = await engine.search("python")
        assert "results" in result

    async def test_learning_stats(self) -> None:
        engine = LearningEngine()
        for _ in range(10):
            await engine.record(_make_record(success=True))
        stats = await engine.learning_stats()
        assert stats.total_experiences == 10
        assert stats.overall_success_rate == 1.0

    async def test_rank_agents(self) -> None:
        engine = LearningEngine()
        for _ in range(5):
            await engine.record(_make_record(agent_id="a", success=True))
        for _ in range(3):
            await engine.record(_make_record(agent_id="b", success=False))
        ranked = await engine.rank_agents()
        assert ranked[0]["agent_id"] == "a"

    async def test_recommend(self) -> None:
        engine = LearningEngine()
        for _ in range(5):
            await engine.record(_make_record(
                agent_id="best", success=True, capabilities=["code.generate"],
            ))
        rec = await engine.recommend_agent_for_capability("code.generate")
        assert rec is not None
        assert rec["recommended_agent_id"] == "best"

    async def test_export_json(self) -> None:
        engine = LearningEngine()
        await engine.record(_make_record())
        exported = await engine.export_json()
        data = json.loads(exported)
        assert len(data) == 1

    async def test_export_csv(self) -> None:
        engine = LearningEngine()
        await engine.record(_make_record())
        exported = await engine.export_csv()
        assert "experience_id" in exported

    async def test_replay_dry_run(self) -> None:
        engine = LearningEngine()
        r = await engine.record(_make_record())
        result = await engine.replay(r.experience_id, mode=ReplayMode.DRY_RUN)
        assert result.error is None

    async def test_start_with_bus(self) -> None:
        engine = LearningEngine()
        bus = InMemoryEventBus()
        await engine.start(bus)
        # Verify collector is subscribed
        assert engine.collector._subscribed is True

    async def test_rebuild_index(self) -> None:
        engine = LearningEngine()
        for i in range(5):
            await engine.record(_make_record(goal=f"goal {i}"))
        count = await engine.rebuild_index()
        assert count == 5

    async def test_trends(self) -> None:
        engine = LearningEngine()
        for _ in range(5):
            await engine.record(_make_record())
        trends = await engine.trends(days=30)
        assert isinstance(trends, list)

    async def test_discover_patterns(self) -> None:
        engine = LearningEngine()
        for _ in range(5):
            await engine.record(_make_record(
                agent_id="a", success=True, capabilities=["code.generate"],
            ))
        report = await engine.discover_patterns()
        assert len(report.success_patterns) >= 1

    async def test_enforce_retention(self) -> None:
        engine = LearningEngine()
        for _ in range(3):
            await engine.record(_make_record())
        result = await engine.enforce_retention()
        assert "remaining_count" in result


# ============================================================
# Integration: Collector → Store → Analyzer
# ============================================================


@pytest.mark.offline
class TestExperienceIntegration:
    """End-to-end integration tests."""

    async def test_full_lifecycle(self) -> None:
        """Test: events → collector → store → analyzer → scorer."""
        engine = LearningEngine()
        bus = InMemoryEventBus()
        await engine.start(bus)

        # Simulate 5 task lifecycles
        for i in range(5):
            task_id = uuid4()
            await bus.publish(_make_event(
                "task.submitted",
                {"task_id": str(task_id), "goal": f"generate python function {i}"},
            ))
            await bus.publish(_make_event(
                "agent.dispatched",
                {"task_id": str(task_id), "agent_id": f"agent-{i % 2}",
                 "agent_type": "coding", "provider": "openai", "model": "gpt-4o",
                 "capability": "code.generate"},
            ))
            await bus.publish(_make_event(
                "agent.completed",
                {"task_id": str(task_id), "output_summary": f"output {i}",
                 "cost_usd": 0.05, "input_tokens": 100, "output_tokens": 50,
                 "success": i % 4 != 0, "confidence": 0.8},
            ))
            await bus.publish(_make_event(
                "task.completed",
                {"task_id": str(task_id), "outcome": "success" if i % 4 != 0 else "failure",
                 "success": i % 4 != 0,
                 "reflection_score": 0.8, "qa_score": 0.85, "cost_usd": 0.05},
            ))
        await asyncio.sleep(0.2)

        stats = await engine.learning_stats()
        assert stats.total_experiences == 5
        assert stats.agent_count == 2
        assert stats.provider_count == 1

        # Verify ranking works
        ranked = await engine.rank_agents()
        assert len(ranked) == 2

        # Verify search works
        await engine.rebuild_index()
        results = await engine.search("python function")
        assert len(results.get("results", [])) > 0


# ============================================================
# Stress tests
# ============================================================


@pytest.mark.offline
class TestExperienceStress:
    """Stress tests for large datasets."""

    async def test_store_1000_records(self) -> None:
        store = ExperienceStore()
        for i in range(1000):
            await store.store(_make_record(
                agent_id=f"agent-{i % 10}",
                goal=f"goal {i}",
                success=i % 5 != 0,
            ))
        assert await store.count() == 1000
        summary = await store.summarize()
        assert summary.total_count == 1000
        assert summary.success_rate == 0.8

    async def test_index_500_records(self) -> None:
        store = ExperienceStore()
        for i in range(500):
            await store.store(_make_record(goal=f"python function number {i}"))
        indexer = ExperienceIndexer(store)
        count = await indexer.rebuild()
        assert count == 500
        results = await indexer.search("python function")
        assert len(results) > 0

    async def test_concurrent_stores(self) -> None:
        """10 concurrent stores should all succeed."""
        store = ExperienceStore()
        records = [_make_record(agent_id=f"agent-{i}") for i in range(10)]
        await asyncio.gather(*[store.store(r) for r in records])
        assert await store.count() == 10
