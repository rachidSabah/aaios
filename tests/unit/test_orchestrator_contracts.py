"""Tests for the orchestrator contracts — Plan, Step, DAG, RetryPolicy, ApprovalGate, Checkpoint."""

from __future__ import annotations

from uuid import uuid4

import pytest

from orchestrator.contracts import (
    ApprovalGate,
    BackoffStrategy,
    Checkpoint,
    DAGValidationError,
    GateTimeoutAction,
    GateType,
    Plan,
    PlanStatus,
    RetryPolicy,
    ScheduleSpec,
    ScheduleType,
    Step,
    StepStatus,
    StepType,
)
from orchestrator.dag import DAGValidator, validate_dag


@pytest.mark.offline
class TestStep:
    """Step contract tests."""

    def test_step_defaults(self) -> None:
        step = Step(goal="do thing", capability="code.read")
        assert step.id is not None
        assert step.goal == "do thing"
        assert step.capability == "code.read"
        assert step.status == StepStatus.PENDING
        assert step.step_type == StepType.AGENT
        assert step.depends_on == []
        assert step.approval_gate is None
        assert step.retry_policy is None

    def test_step_with_dependencies(self) -> None:
        dep1 = uuid4()
        dep2 = uuid4()
        step = Step(goal="x", capability="code.write", depends_on=[dep1, dep2])
        assert step.depends_on == [dep1, dep2]

    def test_step_status_is_mutable(self) -> None:
        step = Step(goal="x", capability="code.read")
        step.status = StepStatus.RUNNING
        assert step.status == StepStatus.RUNNING
        step.status = StepStatus.SUCCEEDED
        assert step.status == StepStatus.SUCCEEDED

    def test_step_with_approval_gate(self) -> None:
        gate = ApprovalGate(gate_type=GateType.PRE_STEP, message="Approve?")
        step = Step(goal="x", capability="code.write", approval_gate=gate)
        assert step.approval_gate is not None
        assert step.approval_gate.gate_type == GateType.PRE_STEP


@pytest.mark.offline
class TestPlan:
    """Plan contract tests."""

    def test_plan_defaults(self) -> None:
        task_id = uuid4()
        plan = Plan(task_id=task_id)
        assert plan.id is not None
        assert plan.task_id == task_id
        assert plan.steps == []
        assert plan.status == PlanStatus.PENDING
        assert plan.variables == {}
        assert plan.priority == "normal"

    def test_step_by_id(self) -> None:
        s1 = Step(id=uuid4(), goal="x", capability="code.read")
        s2 = Step(id=uuid4(), goal="y", capability="code.write")
        plan = Plan(task_id=uuid4(), steps=[s1, s2])
        assert plan.step_by_id(s1.id) is s1
        assert plan.step_by_id(s2.id) is s2
        assert plan.step_by_id(uuid4()) is None

    def test_ready_steps(self) -> None:
        s1 = Step(id=uuid4(), goal="x", capability="code.read")
        s2 = Step(id=uuid4(), goal="y", capability="code.write", depends_on=[s1.id])
        plan = Plan(task_id=uuid4(), steps=[s1, s2])
        # Initially, only s1 is ready (no deps)
        ready = plan.ready_steps()
        assert len(ready) == 1
        assert ready[0].id == s1.id
        # After s1 succeeds, s2 becomes ready
        s1.status = StepStatus.SUCCEEDED
        ready = plan.ready_steps()
        assert len(ready) == 1
        assert ready[0].id == s2.id

    def test_is_complete(self) -> None:
        s1 = Step(id=uuid4(), goal="x", capability="code.read")
        plan = Plan(task_id=uuid4(), steps=[s1])
        assert not plan.is_complete()
        s1.status = StepStatus.SUCCEEDED
        assert plan.is_complete()
        s1.status = StepStatus.FAILED
        assert plan.is_complete()
        s1.status = StepStatus.RUNNING
        assert not plan.is_complete()


@pytest.mark.offline
class TestRetryPolicy:
    """RetryPolicy tests."""

    def test_defaults(self) -> None:
        policy = RetryPolicy()
        assert policy.max_attempts == 3
        assert policy.backoff == BackoffStrategy.EXPONENTIAL
        assert policy.initial_delay_s == 1.0
        assert policy.max_delay_s == 60.0
        assert "transient" in policy.retryable_errors
        assert "permission_denied" in policy.non_retryable_errors

    def test_should_retry_retryable(self) -> None:
        policy = RetryPolicy()
        assert policy.should_retry("transient", 1) is True
        assert policy.should_retry("timeout", 1) is True
        assert policy.should_retry("rate_limit", 1) is True

    def test_should_retry_non_retryable(self) -> None:
        policy = RetryPolicy()
        assert policy.should_retry("permission_denied", 1) is False
        assert policy.should_retry("validation_error", 1) is False

    def test_should_retry_max_attempts(self) -> None:
        policy = RetryPolicy(max_attempts=3)
        assert policy.should_retry("transient", 1) is True
        assert policy.should_retry("transient", 2) is True
        assert policy.should_retry("transient", 3) is False  # at max

    def test_should_retry_unknown_category(self) -> None:
        """Unknown error categories default to retry (safer for transient issues)."""
        policy = RetryPolicy()
        assert policy.should_retry("unknown_error", 1) is True

    def test_delay_constant(self) -> None:
        policy = RetryPolicy(
            backoff=BackoffStrategy.CONSTANT,
            initial_delay_s=2.0,
        )
        assert policy.delay_for_attempt(1) == 2.0
        assert policy.delay_for_attempt(2) == 2.0
        assert policy.delay_for_attempt(5) == 2.0

    def test_delay_linear(self) -> None:
        policy = RetryPolicy(
            backoff=BackoffStrategy.LINEAR,
            initial_delay_s=1.0,
        )
        assert policy.delay_for_attempt(1) == 1.0
        assert policy.delay_for_attempt(2) == 2.0
        assert policy.delay_for_attempt(3) == 3.0

    def test_delay_exponential(self) -> None:
        policy = RetryPolicy(
            backoff=BackoffStrategy.EXPONENTIAL,
            initial_delay_s=1.0,
        )
        assert policy.delay_for_attempt(1) == 1.0
        assert policy.delay_for_attempt(2) == 2.0
        assert policy.delay_for_attempt(3) == 4.0
        assert policy.delay_for_attempt(4) == 8.0

    def test_delay_capped_at_max(self) -> None:
        policy = RetryPolicy(
            backoff=BackoffStrategy.EXPONENTIAL,
            initial_delay_s=10.0,
            max_delay_s=50.0,
        )
        assert policy.delay_for_attempt(1) == 10.0
        assert policy.delay_for_attempt(2) == 20.0
        assert policy.delay_for_attempt(3) == 40.0
        assert policy.delay_for_attempt(4) == 50.0  # capped
        assert policy.delay_for_attempt(5) == 50.0  # capped


@pytest.mark.offline
class TestApprovalGate:
    """ApprovalGate tests."""

    def test_defaults(self) -> None:
        gate = ApprovalGate(message="Approve?")
        assert gate.gate_type == GateType.PRE_STEP
        assert gate.required_role == "operator"
        assert gate.timeout_s == 300
        assert gate.on_timeout == GateTimeoutAction.PAUSE
        assert gate.message == "Approve?"

    def test_frozen(self) -> None:
        gate = ApprovalGate(message="x")
        with pytest.raises(Exception):
            gate.message = "y"  # type: ignore[misc]


@pytest.mark.offline
class TestCheckpoint:
    """Checkpoint tests."""

    def test_defaults(self) -> None:
        cp = Checkpoint(
            id=uuid4(),
            task_id=uuid4(),
            plan_id=uuid4(),
            step_id=uuid4(),
            step_goal="do thing",
            step_status=StepStatus.SUCCEEDED,
        )
        assert cp.agent_id is None
        assert cp.capability == ""
        assert cp.inputs == {}
        assert cp.output is None
        assert cp.error is None
        assert cp.agent_states == {}
        assert cp.cost_usd_so_far == 0.0
        assert cp.sequence == 0
        assert cp.created_at is not None


@pytest.mark.offline
class TestScheduleSpec:
    """ScheduleSpec tests."""

    def test_one_time_valid(self) -> None:
        from datetime import timedelta

        from core.contracts.timestamp import utc_now

        spec = ScheduleSpec(
            schedule_type=ScheduleType.ONE_TIME,
            run_at=utc_now() + timedelta(hours=1),
        )
        assert spec.validate_spec() == []

    def test_one_time_missing_run_at(self) -> None:
        spec = ScheduleSpec(schedule_type=ScheduleType.ONE_TIME)
        errors = spec.validate_spec()
        assert len(errors) == 1
        assert "run_at" in errors[0]

    def test_cron_valid(self) -> None:
        spec = ScheduleSpec(schedule_type=ScheduleType.CRON, cron="0 9 * * 1-5")
        assert spec.validate_spec() == []

    def test_cron_invalid_fields(self) -> None:
        spec = ScheduleSpec(schedule_type=ScheduleType.CRON, cron="not a cron")
        errors = spec.validate_spec()
        assert len(errors) >= 1

    def test_cron_missing(self) -> None:
        spec = ScheduleSpec(schedule_type=ScheduleType.CRON)
        errors = spec.validate_spec()
        assert len(errors) == 1
        assert "cron" in errors[0]

    def test_interval_valid(self) -> None:
        spec = ScheduleSpec(schedule_type=ScheduleType.INTERVAL, interval_s=3600)
        assert spec.validate_spec() == []

    def test_interval_missing(self) -> None:
        spec = ScheduleSpec(schedule_type=ScheduleType.INTERVAL)
        errors = spec.validate_spec()
        assert len(errors) == 1
        assert "interval_s" in errors[0]

    def test_one_time_in_past(self) -> None:
        from datetime import timedelta

        from core.contracts.timestamp import utc_now

        spec = ScheduleSpec(
            schedule_type=ScheduleType.ONE_TIME,
            run_at=utc_now() - timedelta(hours=1),
        )
        errors = spec.validate_spec()
        assert any("past" in e for e in errors)


@pytest.mark.offline
class TestDAGValidator:
    """DAG validator tests."""

    def test_valid_dag(self) -> None:
        s1 = Step(id=uuid4(), goal="x", capability="code.read")
        s2 = Step(id=uuid4(), goal="y", capability="code.write", depends_on=[s1.id])
        plan = Plan(task_id=uuid4(), steps=[s1, s2])
        errors = DAGValidator.validate(plan)
        assert errors == []

    def test_missing_dependency(self) -> None:
        s1 = Step(id=uuid4(), goal="x", capability="code.read", depends_on=[uuid4()])
        plan = Plan(task_id=uuid4(), steps=[s1])
        errors = DAGValidator.validate(plan)
        assert len(errors) >= 1
        assert any("non-existent" in e.reason for e in errors)

    def test_cycle_detected(self) -> None:
        """A -> B -> A is a cycle."""
        s1 = Step(id=uuid4(), goal="A", capability="code.read")
        s2 = Step(id=uuid4(), goal="B", capability="code.write", depends_on=[s1.id])
        s1.depends_on = [s2.id]  # cycle: A -> B -> A
        plan = Plan(task_id=uuid4(), steps=[s1, s2])
        errors = DAGValidator.validate(plan)
        assert any("Cycle" in e.reason for e in errors)

    def test_unreachable_step(self) -> None:
        """A step with a dependency on a non-existent step is unreachable."""
        s1 = Step(id=uuid4(), goal="A", capability="code.read")  # root
        s2 = Step(id=uuid4(), goal="B", capability="code.write", depends_on=[s1.id])
        # s3 has no deps and nothing depends on it — but it's still reachable (it's a root)
        s3 = Step(id=uuid4(), goal="C", capability="code.read")
        plan = Plan(task_id=uuid4(), steps=[s1, s2, s3])
        errors = DAGValidator.validate(plan)
        # s3 is a root (no deps), so it's reachable from itself
        assert errors == []

    def test_validate_dag_raises_on_invalid(self) -> None:
        s1 = Step(id=uuid4(), goal="x", capability="code.read", depends_on=[uuid4()])
        plan = Plan(task_id=uuid4(), steps=[s1])
        with pytest.raises(DAGValidationError):
            validate_dag(plan)

    def test_validate_dag_passes_on_valid(self) -> None:
        s1 = Step(id=uuid4(), goal="x", capability="code.read")
        plan = Plan(task_id=uuid4(), steps=[s1])
        validate_dag(plan)  # should not raise
