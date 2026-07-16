"""Comprehensive tests for the Autonomous Mission & Organization System (v3.0)."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from services.organization import (
    CollaborationEngine,
    DecisionEngine,
    IllegalTransitionError,
    Mission,
    MissionFilter,
    MissionManager,
    MissionPriority,
    MissionStateMachine,
    MissionStatus,
    MissionStore,
    ResourceManager,
    ResourcePool,
    WBSNode,
    WBSType,
    WorkBreakdownEngine,
)


def _make_mission(
    *,
    title: str = "Test Mission",
    objectives: list[str] | None = None,
    budget_total_usd: float = 100.0,
    priority: str = MissionPriority.NORMAL.value,
) -> Mission:
    return Mission(
        title=title,
        description="Test mission description",
        objectives=objectives or ["Objective 1", "Objective 2"],
        priority=priority,
        budget=__import__("services.organization.models", fromlist=["Budget"]).Budget(
            total_usd=budget_total_usd,
        ),
    )


# ============================================================
# Models
# ============================================================


@pytest.mark.offline
class TestMissionModels:
    """Mission model tests."""

    def test_mission_creation(self) -> None:
        m = _make_mission()
        assert m.title == "Test Mission"
        assert m.status == MissionStatus.CREATED.value
        assert len(m.objectives) == 2

    def test_mission_to_dict_and_from_dict(self) -> None:
        m = _make_mission(objectives=["Build", "Test"])
        d = m.to_dict()
        assert d["title"] == "Test Mission"
        restored = Mission.from_dict(d)
        assert restored.title == m.title
        assert restored.objectives == m.objectives

    def test_wbs_node_creation(self) -> None:
        node = WBSNode(
            node_type=WBSType.TASK.value,
            title="Test task",
            capabilities_required=["code.generate"],
        )
        assert node.node_type == "task"
        assert node.status == "pending"

    def test_budget_utilization(self) -> None:
        from services.organization.models import Budget
        b = Budget(total_usd=100.0, spent_usd=50.0)
        assert b.utilization_pct == 50.0
        assert b.remaining_usd == 50.0
        assert not b.is_over_budget

    def test_quality_composite_score(self) -> None:
        from services.organization.models import QualityMetrics
        q = QualityMetrics(reflection_score=0.8, qa_score=0.8, user_satisfaction=0.8)
        assert q.composite_score == pytest.approx(0.8, abs=0.01)

    def test_risk_score(self) -> None:
        from services.organization.models import Risk
        r = Risk(probability=0.8, impact=0.6)
        assert r.risk_score == pytest.approx(0.48, abs=0.01)


# ============================================================
# State Machine
# ============================================================


@pytest.mark.offline
class TestMissionStateMachine:
    """MissionStateMachine tests."""

    def test_valid_transition(self) -> None:
        sm = MissionStateMachine()
        m = _make_mission()
        sm.transition(m, MissionStatus.PLANNING.value)
        assert m.status == MissionStatus.PLANNING.value

    def test_invalid_transition(self) -> None:
        sm = MissionStateMachine()
        m = _make_mission()
        with pytest.raises(IllegalTransitionError):
            sm.transition(m, MissionStatus.COMPLETED.value)  # can't go created→completed

    def test_terminal_states(self) -> None:
        sm = MissionStateMachine()
        assert sm.is_terminal(MissionStatus.COMPLETED.value)
        assert sm.is_terminal(MissionStatus.CANCELLED.value)
        assert not sm.is_terminal(MissionStatus.EXECUTING.value)

    def test_full_lifecycle(self) -> None:
        sm = MissionStateMachine()
        m = _make_mission()
        sm.transition(m, MissionStatus.PLANNING.value)
        sm.transition(m, MissionStatus.READY.value)
        sm.transition(m, MissionStatus.EXECUTING.value)
        sm.transition(m, MissionStatus.PAUSED.value)
        sm.transition(m, MissionStatus.EXECUTING.value)
        sm.transition(m, MissionStatus.COMPLETED.value)
        assert m.status == MissionStatus.COMPLETED.value
        assert m.completed_at is not None

    def test_cancel_from_any_state(self) -> None:
        sm = MissionStateMachine()
        for state in [MissionStatus.CREATED.value, MissionStatus.PLANNING.value,
                      MissionStatus.READY.value, MissionStatus.EXECUTING.value,
                      MissionStatus.PAUSED.value]:
            m = _make_mission()
            m.status = state
            sm.transition(m, MissionStatus.CANCELLED.value)
            assert m.status == MissionStatus.CANCELLED.value

    def test_replan_from_failed(self) -> None:
        sm = MissionStateMachine()
        m = _make_mission()
        m.status = MissionStatus.FAILED.value
        sm.transition(m, MissionStatus.PLANNING.value)
        assert m.status == MissionStatus.PLANNING.value


# ============================================================
# Store
# ============================================================


@pytest.mark.offline
class TestMissionStore:
    """MissionStore tests."""

    async def test_create_and_get(self) -> None:
        store = MissionStore()
        m = _make_mission()
        await store.create(m)
        fetched = await store.get(m.mission_id)
        assert fetched.title == m.title

    async def test_get_not_found(self) -> None:
        store = MissionStore()
        with pytest.raises(Exception):
            await store.get("nonexistent")

    async def test_query_all(self) -> None:
        store = MissionStore()
        for i in range(5):
            await store.create(_make_mission(title=f"Mission {i}"))
        missions = await store.query()
        assert len(missions) == 5

    async def test_query_by_status(self) -> None:
        store = MissionStore()
        m1 = _make_mission(title="M1")
        m2 = _make_mission(title="M2")
        m2.status = MissionStatus.EXECUTING.value
        await store.create(m1)
        await store.create(m2)
        executing = await store.query(MissionFilter(status=MissionStatus.EXECUTING.value))
        assert len(executing) == 1
        assert executing[0].title == "M2"

    async def test_delete(self) -> None:
        store = MissionStore()
        m = _make_mission()
        await store.create(m)
        assert await store.delete(m.mission_id) is True
        assert await store.delete(m.mission_id) is False

    async def test_summarize(self) -> None:
        store = MissionStore()
        for _ in range(3):
            await store.create(_make_mission())
        summary = await store.summarize()
        assert summary.total_missions == 3

    async def test_persistence(self, tmp_path: Path) -> None:
        store1 = MissionStore(storage_dir=tmp_path)
        m = _make_mission(title="Persistent")
        await store1.create(m)
        store2 = MissionStore(storage_dir=tmp_path)
        fetched = await store2.get(m.mission_id)
        assert fetched.title == "Persistent"


# ============================================================
# WBS Engine
# ============================================================


@pytest.mark.offline
class TestWorkBreakdownEngine:
    """WorkBreakdownEngine tests."""

    def test_decompose_flat(self) -> None:
        engine = WorkBreakdownEngine()
        m = _make_mission(objectives=["Build", "Test", "Deploy"])
        engine.decompose(m, strategy="flat")
        assert len(m.wbs_nodes) == 3
        assert all(n.node_type == WBSType.TASK.value for n in m.wbs_nodes)

    def test_decompose_single_project(self) -> None:
        engine = WorkBreakdownEngine()
        m = _make_mission(objectives=["Build", "Test"])
        engine.decompose(m, strategy="single_project")
        # 1 project + 2 tasks
        assert len(m.wbs_nodes) == 3
        assert any(n.node_type == WBSType.PROJECT.value for n in m.wbs_nodes)

    def test_decompose_objective_per_project(self) -> None:
        engine = WorkBreakdownEngine()
        m = _make_mission(objectives=["Build", "Test"])
        engine.decompose(m, strategy="objective_per_project")
        # 2 projects + 2 epics + 10 tasks (5 per epic)
        assert len(m.wbs_nodes) == 14

    def test_add_node(self) -> None:
        engine = WorkBreakdownEngine()
        m = _make_mission()
        node = engine.add_node(m, WBSType.TASK.value, title="Manual task")
        assert node.title == "Manual task"
        assert len(m.wbs_nodes) == 1

    def test_validate_dag_no_cycle(self) -> None:
        engine = WorkBreakdownEngine()
        m = _make_mission()
        n1 = engine.add_node(m, WBSType.TASK.value, title="T1")
        engine.add_node(m, WBSType.TASK.value, title="T2", depends_on=[n1.node_id])
        errors = engine.validate_dag(m)
        assert len(errors) == 0

    def test_validate_dag_with_cycle(self) -> None:
        engine = WorkBreakdownEngine()
        m = _make_mission()
        n1 = engine.add_node(m, WBSType.TASK.value, title="T1")
        n2 = engine.add_node(m, WBSType.TASK.value, title="T2", depends_on=[n1.node_id])
        n1.depends_on.append(n2.node_id)  # create cycle
        errors = engine.validate_dag(m)
        assert len(errors) > 0

    def test_topological_order(self) -> None:
        engine = WorkBreakdownEngine()
        m = _make_mission()
        n1 = engine.add_node(m, WBSType.TASK.value, title="T1")
        n2 = engine.add_node(m, WBSType.TASK.value, title="T2", depends_on=[n1.node_id])
        n3 = engine.add_node(m, WBSType.TASK.value, title="T3", depends_on=[n2.node_id])
        order = engine.topological_order(m)
        assert order.index(n1.node_id) < order.index(n2.node_id)
        assert order.index(n2.node_id) < order.index(n3.node_id)

    def test_execution_layers(self) -> None:
        engine = WorkBreakdownEngine()
        m = _make_mission()
        n1 = engine.add_node(m, WBSType.TASK.value, title="T1")
        n2 = engine.add_node(m, WBSType.TASK.value, title="T2", depends_on=[n1.node_id])
        n3 = engine.add_node(m, WBSType.TASK.value, title="T3")  # independent
        layers = engine.get_execution_layers(m)
        assert len(layers) == 2  # n1+n3 in layer 0, n2 in layer 1
        assert n1.node_id in layers[0]
        assert n3.node_id in layers[0]
        assert n2.node_id in layers[1]

    def test_merge_tasks(self) -> None:
        engine = WorkBreakdownEngine()
        m = _make_mission()
        n1 = engine.add_node(m, WBSType.TASK.value, title="T1")
        n2 = engine.add_node(m, WBSType.TASK.value, title="T2")
        merged = engine.merge_tasks(m, n1.node_id, n2.node_id, new_title="Merged")
        assert merged is not None
        assert merged.title == "Merged"
        assert len(m.wbs_nodes) == 1

    def test_split_task(self) -> None:
        engine = WorkBreakdownEngine()
        m = _make_mission()
        n = engine.add_node(m, WBSType.TASK.value, title="Original")
        subtasks = engine.split_task(m, n.node_id, sub_tasks=[
            {"title": "Sub1"}, {"title": "Sub2"},
        ])
        assert len(subtasks) == 2
        assert all(s.node_type == WBSType.SUBTASK.value for s in subtasks)


# ============================================================
# Decision Engine
# ============================================================


@pytest.mark.offline
class TestDecisionEngine:
    """DecisionEngine tests."""

    def test_evaluate_normal_mission(self) -> None:
        engine = DecisionEngine()
        m = _make_mission()
        m.status = MissionStatus.EXECUTING.value
        recs = engine.evaluate(m)
        # Should return at least a "continue" recommendation
        assert len(recs) >= 1
        assert any(r.decision_type == "continue" for r in recs)

    def test_evaluate_over_budget(self) -> None:
        engine = DecisionEngine()
        m = _make_mission(budget_total_usd=10.0)
        m.budget.spent_usd = 15.0  # over budget
        m.status = MissionStatus.EXECUTING.value
        recs = engine.evaluate(m)
        assert any(r.decision_type == "pause" and r.should_act for r in recs)

    def test_evaluate_deadline_passed(self) -> None:
        engine = DecisionEngine()
        m = _make_mission()
        m.deadline = datetime.now(UTC) - timedelta(hours=1)
        m.status = MissionStatus.EXECUTING.value
        m.started_at = datetime.now(UTC) - timedelta(hours=2)
        recs = engine.evaluate(m)
        assert any(r.decision_type in ("cancel", "replan") for r in recs)

    def test_should_start_mission(self) -> None:
        engine = DecisionEngine()
        m = _make_mission()
        # Add WBS nodes so the mission is ready
        from services.organization import WorkBreakdownEngine
        WorkBreakdownEngine().decompose(m, strategy="flat")
        rec = engine.should_start_mission(m)
        assert rec.should_act is True

    def test_should_start_mission_no_objectives(self) -> None:
        engine = DecisionEngine()
        m = _make_mission(objectives=[])
        rec = engine.should_start_mission(m)
        assert rec.should_act is False

    def test_collect_evidence(self) -> None:
        engine = DecisionEngine()
        m = _make_mission()
        m.status = MissionStatus.EXECUTING.value
        evidence = engine.collect_evidence(m)
        assert evidence.mission_status == MissionStatus.EXECUTING.value


# ============================================================
# Collaboration Engine
# ============================================================


@pytest.mark.offline
class TestCollaborationEngine:
    """CollaborationEngine tests."""

    async def test_send_and_receive_message(self) -> None:
        from services.organization.collaboration import AgentMessage, MessageType
        engine = CollaborationEngine()
        msg = AgentMessage(
            message_type=MessageType.DIRECT.value,
            from_agent_id="agent-a",
            to_agent_id="agent-b",
            content="Hello",
        )
        await engine.send_message(msg)
        received = await engine.get_messages("agent-b")
        assert len(received) == 1
        assert received[0].content == "Hello"

    async def test_broadcast_message(self) -> None:
        from services.organization.collaboration import AgentMessage, MessageType
        engine = CollaborationEngine()
        msg = AgentMessage(
            message_type=MessageType.BROADCAST.value,
            from_agent_id="agent-a",
            to_agent_id=None,
            content="Broadcast",
        )
        await engine.send_message(msg)
        received_a = await engine.get_messages("agent-a")
        received_b = await engine.get_messages("agent-b")
        # Broadcast goes to all agents
        assert any(m.content == "Broadcast" for m in received_a)
        assert any(m.content == "Broadcast" for m in received_b)

    async def test_voting(self) -> None:
        from services.organization.collaboration import Vote
        engine = CollaborationEngine()
        votes = [
            Vote(agent_id="a", vote="yes"),
            Vote(agent_id="b", vote="yes"),
            Vote(agent_id="c", vote="no"),
        ]
        result = await engine.conduct_vote(
            "Should we proceed?", ["a", "b", "c"], votes=votes,
        )
        assert result.passed is True
        assert result.yes_count == 2

    async def test_consensus(self) -> None:
        engine = CollaborationEngine()
        result = await engine.seek_consensus(
            "Architecture",
            ["a", "b", "c"],
            positions={"a": "microservices", "b": "microservices", "c": "microservices"},
        )
        assert result.consensus_reached is True

    async def test_peer_review(self) -> None:
        from services.organization.collaboration import ReviewVerdict
        engine = CollaborationEngine()
        review = await engine.request_peer_review(
            reviewer_agent_id="reviewer",
            reviewed_agent_id="worker",
            verdict=ReviewVerdict.APPROVED.value,
            quality_score=0.9,
        )
        assert review.verdict == ReviewVerdict.APPROVED.value

    async def test_delegation(self) -> None:
        from services.organization.collaboration import DelegationRequest
        engine = CollaborationEngine()
        req = DelegationRequest(
            from_agent_id="agent-a",
            to_agent_id="agent-b",
            task_description="Do this task",
        )
        result = await engine.delegate_task(req, accepted=True)
        assert result.accepted is True

    async def test_shared_memory(self) -> None:
        engine = CollaborationEngine()
        await engine.update_shared_memory("mission-1", "key", "value")
        val = await engine.get_shared_memory("mission-1", "key")
        assert val == "value"


# ============================================================
# Resource Manager
# ============================================================


@pytest.mark.offline
class TestResourceManager:
    """ResourceManager tests."""

    async def test_assign_and_release_agent(self) -> None:
        mgr = ResourceManager()
        assignment = await mgr.assign_agent("mission-1", "agent-1")
        assert assignment.is_active
        released = await mgr.release_agent("mission-1", "agent-1")
        assert released

    async def test_acquire_task_slot(self) -> None:
        mgr = ResourceManager(pool=ResourcePool(max_total_concurrent_tasks=2))
        assert await mgr.acquire_task_slot("m1") is True
        assert await mgr.acquire_task_slot("m2") is True
        assert await mgr.acquire_task_slot("m3") is False  # limit reached
        await mgr.release_task_slot("m1")
        assert await mgr.acquire_task_slot("m3") is True

    async def test_budget_reservation(self) -> None:
        mgr = ResourceManager()
        mission = _make_mission(budget_total_usd=100.0)
        assert await mgr.reserve_budget(mission, 30.0) is True
        assert mission.budget.reserved_usd == 30.0
        assert await mgr.reserve_budget(mission, 80.0) is False  # only 70 remaining
        await mgr.release_budget_reservation(mission, 30.0)
        assert mission.budget.reserved_usd == 0.0

    async def test_spend_budget(self) -> None:
        mgr = ResourceManager()
        mission = _make_mission(budget_total_usd=100.0)
        await mgr.reserve_budget(mission, 30.0)
        assert await mgr.spend_budget(mission, 20.0) is True
        assert mission.budget.spent_usd == 20.0

    async def test_select_least_loaded_agent(self) -> None:
        mgr = ResourceManager(pool=ResourcePool(available_agents=["a", "b", "c"]))
        await mgr.assign_agent("m1", "a")
        await mgr.assign_agent("m1", "a")
        await mgr.assign_agent("m1", "b")
        selected = await mgr.select_least_loaded_agent()
        assert selected == "c"  # c has 0 assignments

    async def test_release_all_for_mission(self) -> None:
        mgr = ResourceManager()
        await mgr.assign_agent("m1", "a")
        await mgr.assign_agent("m1", "b")
        count = await mgr.release_all_for_mission("m1")
        assert count == 2


# ============================================================
# MissionManager (Integration)
# ============================================================


@pytest.mark.offline
class TestMissionManager:
    """MissionManager integration tests."""

    async def test_create_and_get(self) -> None:
        mgr = MissionManager()
        await mgr.start()
        m = await mgr.create_mission(
            title="Test Mission",
            objectives=["Build", "Test"],
            budget_total_usd=100.0,
        )
        fetched = await mgr.get_mission(m.mission_id)
        assert fetched.title == "Test Mission"

    async def test_full_lifecycle(self) -> None:
        mgr = MissionManager()
        await mgr.start()
        m = await mgr.create_mission(
            title="Lifecycle Test",
            objectives=["Build"],
            budget_total_usd=50.0,
        )
        # Start
        started = await mgr.start_mission(m.mission_id)
        assert started.status == MissionStatus.EXECUTING.value
        # Pause
        paused = await mgr.pause_mission(m.mission_id, reason="testing")
        assert paused.status == MissionStatus.PAUSED.value
        # Resume
        resumed = await mgr.resume_mission(m.mission_id)
        assert resumed.status == MissionStatus.EXECUTING.value
        # Complete
        completed = await mgr.complete_mission(m.mission_id)
        assert completed.status == MissionStatus.COMPLETED.value

    async def test_cancel(self) -> None:
        mgr = MissionManager()
        await mgr.start()
        m = await mgr.create_mission(title="Cancel Test", objectives=["X"])
        cancelled = await mgr.cancel_mission(m.mission_id, reason="not needed")
        assert cancelled.status == MissionStatus.CANCELLED.value

    async def test_wbs_decomposition(self) -> None:
        mgr = MissionManager()
        await mgr.start()
        m = await mgr.create_mission(
            title="WBS Test",
            objectives=["Build", "Test", "Deploy"],
            decompose=True,
            decomposition_strategy="objective_per_project",
        )
        # 3 objectives → 3 projects + 3 epics + 15 tasks = 21 nodes
        assert len(m.wbs_nodes) == 21

    async def test_add_wbs_node(self) -> None:
        mgr = MissionManager()
        await mgr.start()
        m = await mgr.create_mission(title="WBS Add", objectives=["X"])
        node = await mgr.add_wbs_node(
            m.mission_id, WBSType.TASK.value, title="Manual task",
        )
        assert node.title == "Manual task"

    async def test_evaluate_mission(self) -> None:
        mgr = MissionManager()
        await mgr.start()
        m = await mgr.create_mission(title="Eval Test", objectives=["X"])
        await mgr.start_mission(m.mission_id)
        recs = await mgr.evaluate_mission(m.mission_id)
        assert len(recs) >= 1

    async def test_get_timeline(self) -> None:
        mgr = MissionManager()
        await mgr.start()
        m = await mgr.create_mission(title="Timeline Test", objectives=["X"])
        await mgr.start_mission(m.mission_id)
        await mgr.complete_mission(m.mission_id)
        timeline = await mgr.get_mission_timeline(m.mission_id)
        assert len(timeline) >= 2  # at least created + started

    async def test_get_graph(self) -> None:
        mgr = MissionManager()
        await mgr.start()
        m = await mgr.create_mission(title="Graph Test", objectives=["X"])
        graph = await mgr.get_mission_graph(m.mission_id)
        assert graph["node_count"] > 0

    async def test_portfolio_metrics(self) -> None:
        mgr = MissionManager()
        await mgr.start()
        for i in range(3):
            await mgr.create_mission(title=f"Mission {i}", objectives=["X"])
        metrics = await mgr.get_portfolio_metrics()
        assert metrics.total_missions >= 3

    async def test_search(self) -> None:
        mgr = MissionManager()
        await mgr.start()
        await mgr.create_mission(
            title="Python web app",
            objectives=["Build backend", "Build frontend"],
        )
        await mgr.create_mission(
            title="Data pipeline",
            objectives=["Build ETL"],
        )
        results = await mgr.search_missions("python web")
        assert len(results) >= 1

    async def test_replay(self) -> None:
        mgr = MissionManager()
        await mgr.start()
        m = await mgr.create_mission(title="Replay Test", objectives=["X"])
        await mgr.start_mission(m.mission_id)
        await mgr.complete_mission(m.mission_id)
        result = await mgr.replay_mission(m.mission_id)
        assert result.mission_id == m.mission_id

    async def test_persistence_and_recovery(self, tmp_path: Path) -> None:
        # Create a manager with persistent storage
        mgr1 = MissionManager(storage_dir=tmp_path)
        await mgr1.start()
        m = await mgr1.create_mission(title="Persistent Mission", objectives=["X"])
        await mgr1.start_mission(m.mission_id)

        # New manager recovers from disk
        mgr2 = MissionManager(storage_dir=tmp_path)
        await mgr2.start()
        # The mission should be recovered (in PAUSED state since it was EXECUTING)
        recovered = await mgr2.list_missions()
        assert len(recovered) >= 1
        assert any(rm.title == "Persistent Mission" for rm in recovered)


# ============================================================
# Stress Tests
# ============================================================


@pytest.mark.offline
class TestMissionStress:
    """Stress tests for the mission system."""

    async def test_create_100_missions(self) -> None:
        mgr = MissionManager()
        await mgr.start()
        for i in range(100):
            await mgr.create_mission(
                title=f"Mission {i}",
                objectives=[f"Objective {i}"],
                budget_total_usd=10.0,
            )
        missions = await mgr.list_missions()
        assert len(missions) >= 100

    async def test_mission_with_100_wbs_nodes(self) -> None:
        mgr = MissionManager()
        await mgr.start()
        objectives = [f"Objective {i}" for i in range(20)]
        m = await mgr.create_mission(
            title="Large Mission",
            objectives=objectives,
            decompose=True,
        )
        # 20 objectives → 20 projects + 20 epics + 100 tasks = 140 nodes
        assert len(m.wbs_nodes) >= 100

    async def test_concurrent_mission_creation(self) -> None:
        mgr = MissionManager()
        await mgr.start()
        async def create(i: int) -> Mission:
            return await mgr.create_mission(
                title=f"Concurrent {i}", objectives=["X"], budget_total_usd=10.0,
            )
        missions = await asyncio.gather(*[create(i) for i in range(20)])
        assert len(missions) == 20
