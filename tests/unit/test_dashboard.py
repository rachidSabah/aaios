"""Tests for the Dashboard Service (workflow store, metrics collector, analytics)."""

from __future__ import annotations

import asyncio
from pathlib import Path
from uuid import uuid4

import pytest

from core.contracts.actor import ActorRef, ActorType
from core.contracts.event import Event
from core.event_bus import InMemoryEventBus
from services.dashboard import (
    Analytics,
    MetricsCollector,
    Workflow,
    WorkflowEdge,
    WorkflowNode,
    WorkflowStore,
    WorkflowValidationError,
)


def _make_event(
    topic: str = "agent.completed",
    payload: dict[str, object] | None = None,
) -> Event:
    """Helper to build a minimal valid Event."""
    return Event(
        topic=topic,
        correlation_id=uuid4(),
        actor=ActorRef(type=ActorType.SYSTEM, id="test"),
        payload=payload or {},
    )



@pytest.mark.offline
class TestWorkflowNode:
    """WorkflowNode tests."""

    def test_to_dict_and_from_dict(self) -> None:
        node = WorkflowNode(
            id="n1",
            capability="code.generate",
            label="Generate code",
            parameters={"language": "python"},
            position={"x": 100.0, "y": 200.0},
        )
        d = node.to_dict()
        assert d["id"] == "n1"
        assert d["capability"] == "code.generate"
        restored = WorkflowNode.from_dict(d)
        assert restored.id == node.id
        assert restored.capability == node.capability
        assert restored.parameters == node.parameters
        assert restored.position == node.position


@pytest.mark.offline
class TestWorkflowValidation:
    """Workflow.validate() tests."""

    def test_valid_dag(self) -> None:
        wf = Workflow(
            id="w1",
            name="Linear",
            nodes=[
                WorkflowNode(id="a", capability="code.generate", label="A"),
                WorkflowNode(id="b", capability="code.review", label="B"),
                WorkflowNode(id="c", capability="code.test", label="C"),
            ],
            edges=[
                WorkflowEdge(source="a", target="b"),
                WorkflowEdge(source="b", target="c"),
            ],
        )
        wf.validate()  # should not raise

    def test_cycle_detection(self) -> None:
        wf = Workflow(
            id="w2",
            name="Cyclic",
            nodes=[
                WorkflowNode(id="a", capability="c", label="A"),
                WorkflowNode(id="b", capability="c", label="B"),
                WorkflowNode(id="c", capability="c", label="C"),
            ],
            edges=[
                WorkflowEdge(source="a", target="b"),
                WorkflowEdge(source="b", target="c"),
                WorkflowEdge(source="c", target="a"),
            ],
        )
        with pytest.raises(WorkflowValidationError, match="cycle"):
            wf.validate()

    def test_duplicate_node_ids(self) -> None:
        wf = Workflow(
            id="w3",
            name="Dup",
            nodes=[
                WorkflowNode(id="a", capability="c", label="A"),
                WorkflowNode(id="a", capability="c", label="B"),
            ],
        )
        with pytest.raises(WorkflowValidationError, match="Duplicate"):
            wf.validate()

    def test_edge_references_missing_node(self) -> None:
        wf = Workflow(
            id="w4",
            name="Missing",
            nodes=[WorkflowNode(id="a", capability="c", label="A")],
            edges=[WorkflowEdge(source="a", target="b")],
        )
        with pytest.raises(WorkflowValidationError, match="not in nodes"):
            wf.validate()

    def test_topological_order(self) -> None:
        wf = Workflow(
            id="w5",
            name="Topo",
            nodes=[
                WorkflowNode(id="a", capability="c", label="A"),
                WorkflowNode(id="b", capability="c", label="B"),
                WorkflowNode(id="c", capability="c", label="C"),
                WorkflowNode(id="d", capability="c", label="D"),
            ],
            edges=[
                WorkflowEdge(source="a", target="b"),
                WorkflowEdge(source="a", target="c"),
                WorkflowEdge(source="b", target="d"),
                WorkflowEdge(source="c", target="d"),
            ],
        )
        order = wf.topological_order()
        assert order[0] == "a"
        assert order[-1] == "d"
        assert set(order) == {"a", "b", "c", "d"}


@pytest.mark.offline
class TestWorkflowStore:
    """WorkflowStore tests."""

    async def test_create_and_get(self) -> None:
        store = WorkflowStore()
        wf = await store.create(
            name="My Workflow",
            description="Test",
            nodes=[WorkflowNode(id="n1", capability="code.generate", label="Gen")],
        )
        fetched = await store.get(wf.id)
        assert fetched.id == wf.id
        assert fetched.name == "My Workflow"
        assert len(fetched.nodes) == 1

    async def test_list(self) -> None:
        store = WorkflowStore()
        await store.create(name="WF1")
        await store.create(name="WF2")
        workflows = await store.list()
        assert len(workflows) == 2

    async def test_update(self) -> None:
        store = WorkflowStore()
        wf = await store.create(name="Original")
        updated = await store.update(wf.id, {"name": "Renamed"})
        assert updated.name == "Renamed"

    async def test_delete(self) -> None:
        store = WorkflowStore()
        wf = await store.create(name="ToDelete")
        result = await store.delete(wf.id)
        assert result is True
        result = await store.delete(wf.id)
        assert result is False

    async def test_add_node_and_edge(self) -> None:
        store = WorkflowStore()
        wf = await store.create(name="Growth")
        await store.add_node(
            wf.id,
            WorkflowNode(id="a", capability="c", label="A"),
        )
        await store.add_node(
            wf.id,
            WorkflowNode(id="b", capability="c", label="B"),
        )
        await store.add_edge(wf.id, WorkflowEdge(source="a", target="b"))
        fetched = await store.get(wf.id)
        assert len(fetched.nodes) == 2
        assert len(fetched.edges) == 1

    async def test_persistence_to_disk(self, tmp_path: Path) -> None:
        store1 = WorkflowStore(storage_dir=tmp_path)
        wf = await store1.create(
            name="Persistent",
            nodes=[WorkflowNode(id="a", capability="c", label="A")],
        )
        # New store loading from same dir should find it
        store2 = WorkflowStore(storage_dir=tmp_path)
        fetched = await store2.get(wf.id)
        assert fetched.name == "Persistent"

    async def test_invalid_workflow_raises(self) -> None:
        store = WorkflowStore()
        with pytest.raises(WorkflowValidationError):
            await store.create(
                name="Bad",
                nodes=[WorkflowNode(id="a", capability="c", label="A")],
                edges=[WorkflowEdge(source="a", target="b")],  # b doesn't exist
            )


@pytest.mark.offline
class TestMetricsCollector:
    """MetricsCollector tests."""

    async def test_record_and_snapshot(self) -> None:
        collector = MetricsCollector(recent_buffer_size=100)
        bus = InMemoryEventBus()
        await collector.subscribe(bus)

        # Publish some events
        for i in range(5):
            event = _make_event(
                topic="agent.dispatched",
                payload={
                    "agent_id": f"agent-{i % 2}",
                    "capability": "code.generate",
                    "duration_s": 0.5 + i * 0.1,
                    "success": i % 3 != 0,
                    "cost_usd": 0.01 * i,
                },
            )
            await bus.publish(event)
            await asyncio.sleep(0.01)  # let dispatch run

        # Give the dispatch tasks a moment
        await asyncio.sleep(0.05)

        snap = await collector.snapshot()
        assert snap.total_events == 5
        assert snap.events_last_minute == 5
        assert "agent-0" in snap.active_agents
        assert "agent-1" in snap.active_agents
        assert "code.generate" in snap.active_capabilities
        assert len(snap.recent_events) <= 20

    async def test_timeseries(self) -> None:
        collector = MetricsCollector()
        # Directly record samples without going through the bus
        for i in range(10):
            sample_event = _make_event(
                topic="agent.completed",
                payload={
                    "agent_id": "a1",
                    "capability": "code.test",
                    "duration_s": 0.2,
                    "success": True,
                    "cost_usd": 0.001,
                },
            )
            await collector.record_event(sample_event)
        series = await collector.timeseries(metric="event_count", window_minutes=60)
        assert len(series) >= 1
        total = sum(s["value"] for s in series)
        assert total == 10

    async def test_buckets_aggregate(self) -> None:
        collector = MetricsCollector()
        for i in range(20):
            await collector.record_event(
                _make_event(
                    topic="task.completed",
                    payload={
                        "agent_id": "a1",
                        "success": i % 4 != 0,  # 75% success rate
                        "duration_s": 1.0,
                        "cost_usd": 0.01,
                    },
                ),
            )
        snap = await collector.snapshot()
        # At least one minute bucket exists
        assert len(snap.buckets_last_hour) >= 1
        bucket = snap.buckets_last_hour[-1]
        assert bucket["sample_count"] == 20
        assert bucket["success_count"] == 15
        assert bucket["failure_count"] == 5
        assert bucket["success_rate"] == 0.75
        assert bucket["total_cost_usd"] == pytest.approx(0.20)


@pytest.mark.offline
class TestAnalytics:
    """Analytics tests."""

    async def test_summary(self) -> None:
        collector = MetricsCollector()
        analytics = Analytics(collector)
        for i in range(10):
            await collector.record_event(
                _make_event(
                    topic="agent.completed",
                    payload={
                        "agent_id": f"a{i % 3}",
                        "capability": "code.generate",
                        "duration_s": 0.5,
                        "success": i != 0,
                        "cost_usd": 0.01,
                    },
                ),
            )
        summary = await analytics.summary()
        assert summary["total_events"] == 10
        assert summary["success_rate"] == pytest.approx(0.9, abs=0.01)
        assert summary["total_cost_usd"] == pytest.approx(0.10)
        assert any(a[0] == "code.generate" for a in summary["top_capabilities"])

    async def test_cost_breakdown(self) -> None:
        collector = MetricsCollector()
        analytics = Analytics(collector)
        await collector.record_event(
            _make_event(
                topic="agent.completed",
                payload={"capability": "code.generate", "cost_usd": 0.05, "duration_s": 1.0},
            ),
        )
        await collector.record_event(
            _make_event(
                topic="agent.completed",
                payload={"capability": "desktop.screenshot", "cost_usd": 0.02, "duration_s": 0.5},
            ),
        )
        breakdown = await analytics.cost_breakdown(window_minutes=60)
        assert breakdown["total_cost_usd"] == pytest.approx(0.07)
        caps = {c["capability"]: c["cost_usd"] for c in breakdown["by_capability"]}
        assert "code.generate" in caps
        assert "desktop.screenshot" in caps

    async def test_latency_percentiles(self) -> None:
        collector = MetricsCollector()
        analytics = Analytics(collector)
        for i in range(20):
            await collector.record_event(
                _make_event(
                    topic="agent.completed",
                    payload={"duration_s": float(i) / 10.0, "success": True},
                ),
            )
        pct = await analytics.latency_percentiles(window_minutes=60)
        assert pct["count"] == 20
        assert 0.0 <= pct["p50"] <= pct["p90"] <= pct["p95"] <= pct["p99"]

    async def test_throughput_series(self) -> None:
        collector = MetricsCollector()
        analytics = Analytics(collector)
        for _ in range(5):
            await collector.record_event(_make_event(topic="agent.completed"))
        series = await analytics.throughput_series(window_minutes=60)
        assert len(series) >= 1
        assert sum(s["value"] for s in series) == 5
