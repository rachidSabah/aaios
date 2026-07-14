"""Tests for core.contracts — the shared Pydantic models."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import pytest

from core.contracts.actor import ActorRef, ActorType
from core.contracts.event import Event, EventTopic
from core.contracts.health import HealthReport, HealthState
from core.contracts.permission import Permission, PermissionDecision
from core.contracts.task import (
    TaskContext,
    TaskProgressKind,
    TaskRequest,
    TaskResult,
    TaskResultStatus,
    TaskStatus,
)
from core.contracts.timestamp import utc_now


@pytest.mark.offline
class TestActorRef:
    """ActorRef tests."""

    def test_user_actor_factory(self) -> None:
        actor = ActorRef.user("alice", display_name="Alice")
        assert actor.type == ActorType.USER
        assert actor.id == "alice"
        assert actor.display_name == "Alice"

    def test_agent_actor_factory(self) -> None:
        actor = ActorRef.agent("claude-code-v1")
        assert actor.type == ActorType.AGENT
        assert actor.id == "claude-code-v1"

    def test_system_actor_factory(self) -> None:
        actor = ActorRef.system()
        assert actor.type == ActorType.SYSTEM
        assert str(actor) == "system:system"

    def test_str_format(self) -> None:
        actor = ActorRef.user("bob")
        assert str(actor) == "user:bob"

    def test_each_instance_has_unique_id(self) -> None:
        a1 = ActorRef.system()
        a2 = ActorRef.system()
        assert a1.instance_id != a2.instance_id


@pytest.mark.offline
class TestEvent:
    """Event tests."""

    def test_event_defaults(self) -> None:
        from uuid import uuid4

        e = Event(
            topic=EventTopic.TASK_CREATED,
            correlation_id=uuid4(),
            actor=ActorRef.system(),
        )
        assert e.id is not None
        assert isinstance(e.id, UUID)
        assert e.sequence == 0
        assert e.timestamp is not None
        assert e.payload == {}
        assert e.causation_id is None

    def test_event_is_frozen(self) -> None:
        from uuid import uuid4

        e = Event(
            topic="test.topic",
            correlation_id=uuid4(),
            actor=ActorRef.system(),
        )
        with pytest.raises(Exception):  # ValidationError or FrozenInstanceError
            e.topic = "other.topic"  # type: ignore[misc]

    def test_derived_event_preserves_correlation(self) -> None:
        from uuid import uuid4

        e1 = Event(
            topic="task.created",
            correlation_id=uuid4(),
            actor=ActorRef.system(),
            payload={"goal": "do x"},
        )
        e2 = e1.derived(topic="task.queued", payload={"queue_pos": 1})
        assert e2.correlation_id == e1.correlation_id
        assert e2.causation_id == e1.id
        assert e2.topic == "task.queued"
        assert e2.payload == {"queue_pos": 1}


@pytest.mark.offline
class TestHealthReport:
    """HealthReport tests."""

    def test_healthy_factory(self) -> None:
        report = HealthReport.healthy(latency_ms=12.5)
        assert report.state == HealthState.HEALTHY
        assert report.latency_ms == 12.5

    def test_degraded_factory(self) -> None:
        report = HealthReport.degraded("disk almost full", ["disk"])
        assert report.state == HealthState.DEGRADED
        assert "disk" in report.failing_subsystems

    def test_unhealthy_factory(self) -> None:
        report = HealthReport.unhealthy("crashed")
        assert report.state == HealthState.UNHEALTHY
        assert report.reason == "crashed"


@pytest.mark.offline
class TestPermission:
    """Permission tests."""

    def test_permission_str_with_wildcard(self) -> None:
        perm = Permission(name="gateway.fs.read")
        assert str(perm) == "gateway.fs.read"

    def test_permission_str_with_resource(self) -> None:
        perm = Permission(name="gateway.fs.read", resource="/etc/passwd")
        assert str(perm) == "gateway.fs.read(/etc/passwd)"

    def test_permission_decision_enum(self) -> None:
        assert PermissionDecision.ALLOW.value == "allow"
        assert PermissionDecision.DENY.value == "deny"
        assert PermissionDecision.ASK.value == "ask"


@pytest.mark.offline
class TestTaskContracts:
    """TaskRequest / TaskResult / TaskProgress tests."""

    def test_task_request_defaults(self) -> None:
        req = TaskRequest(
            goal="write tests",
            context=TaskContext(submitted_by=ActorRef.user("alice")),
        )
        assert req.priority == "normal"
        assert req.id is not None
        assert req.context.budget_usd is None

    def test_task_result_defaults(self) -> None:
        from uuid import uuid4

        result = TaskResult(task_id=uuid4(), status=TaskResultStatus.SUCCESS)
        assert result.cost_usd == 0.0
        assert result.duration_s == 0.0

    def test_task_progress_kind_enum(self) -> None:
        assert TaskProgressKind.STARTED.value == "started"
        assert TaskProgressKind.RESULT.value == "result"

    def test_task_status_enum(self) -> None:
        assert TaskStatus.PENDING.value == "pending"
        assert TaskStatus.COMPLETED.value == "completed"


@pytest.mark.offline
class TestTimestamp:
    """Timestamp helper tests."""

    def test_utc_now_returns_aware_datetime(self) -> None:
        now = utc_now()
        assert now.tzinfo is not None
        # Should be UTC (offset 0)
        assert now.utcoffset().total_seconds() == 0

    def test_utc_now_is_recent(self) -> None:
        before = datetime.now(UTC)
        now = utc_now()
        after = datetime.now(UTC)
        assert before <= now <= after
