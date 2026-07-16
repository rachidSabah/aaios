"""Experience Collector — subscribes to the event bus and builds records from live events.

The collector listens to the AAiOS event bus for task lifecycle events:
  - task.submitted → start tracking a new execution
  - step.started / step.completed → build the execution plan
  - agent.dispatched / agent.completed → record agent + provider
  - task.completed → finalize and store the experience record

The collector maintains in-flight tracking: it accumulates state as events
arrive, then flushes a complete ExperienceRecord to the store when the task
finishes.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any
from uuid import UUID

from core.contracts.event import Event
from core.event_bus import EventBus
from core.logging import get_logger
from services.experience.models import (
    ExecutionStep,
    ExperienceOutcome,
    ExperienceRecord,
    TokenUsage,
)
from services.experience.store import ExperienceStore

_log = get_logger(__name__)

__all__ = ["ExperienceCollector", "InFlightExecution"]


class InFlightExecution:
    """Accumulates state for an execution in progress.

    Created when a task starts; finalized and flushed when the task completes.
    """

    def __init__(self, task_id: UUID, goal: str = "") -> None:
        self.task_id = task_id
        self.goal = goal
        self.workflow_id: str | None = None
        self.correlation_id: UUID | None = None
        self.agent_id: str | None = None
        self.agent_type: str | None = None
        self.provider: str | None = None
        self.model: str | None = None
        self.capabilities_used: list[str] = []
        self.input_summary: str = ""
        self.output_summary: str = ""
        self.plan: list[ExecutionStep] = []
        self.start_time: float = time.time()
        self.end_time: float | None = None
        self.retries: int = 0
        self.reflection_score: float = 0.0
        self.qa_score: float = 0.0
        self.outcome: str = ExperienceOutcome.SUCCESS.value
        self.success: bool = True
        self.failure_reason: str | None = None
        self.recovery_action: str | None = None
        self.cost_usd: float = 0.0
        self.token_usage_input: int = 0
        self.token_usage_output: int = 0
        self.confidence: float = 0.0
        self.metadata: dict[str, Any] = {}

    def add_step(self, step: ExecutionStep) -> None:
        """Add or update a step in the plan."""
        for i, existing in enumerate(self.plan):
            if existing.step_id == step.step_id:
                self.plan[i] = step
                return
        self.plan.append(step)

    def execution_time_s(self) -> float:
        end = self.end_time or time.time()
        return end - self.start_time


class ExperienceCollector:
    """Subscribes to the event bus and builds ExperienceRecords.

    Subscribe once with `await collector.subscribe(bus)`. After that, every
    task lifecycle event is tracked. When a task completes, the collector
    builds an ExperienceRecord and stores it.
    """

    def __init__(
        self,
        store: ExperienceStore,
        *,
        flush_on_outcome: bool = True,
    ) -> None:
        self._store = store
        self._flush_on_outcome = flush_on_outcome
        self._in_flight: dict[UUID, InFlightExecution] = {}
        self._lock = asyncio.Lock()
        self._subscribed = False

    async def subscribe(self, bus: EventBus) -> None:
        """Subscribe to all task lifecycle events on the bus."""
        if self._subscribed:
            return
        bus.subscribe("task", self._handle_event)
        bus.subscribe("agent", self._handle_event)
        bus.subscribe("step", self._handle_event)
        bus.subscribe("experience", self._handle_event)
        self._subscribed = True
        _log.info("ExperienceCollector subscribed to event bus")

    async def _handle_event(self, event: Event) -> None:
        """Route an event to the appropriate handler."""
        try:
            topic = event.topic
            if topic == "task.submitted":
                await self._on_task_submitted(event)
            elif topic == "task.completed":
                await self._on_task_completed(event)
            elif topic == "agent.dispatched":
                await self._on_agent_dispatched(event)
            elif topic == "agent.completed":
                await self._on_agent_completed(event)
            elif topic == "step.started":
                await self._on_step_started(event)
            elif topic == "step.completed":
                await self._on_step_completed(event)
            elif topic == "experience.feedback":
                await self._on_feedback(event)
        except Exception as e:
            _log.warning("ExperienceCollector event handling failed for %s: %s", topic, e)

    async def _on_task_submitted(self, event: Event) -> None:
        """Start tracking a new execution."""
        task_id = self._extract_task_id(event)
        if task_id is None:
            return
        goal = str(event.payload.get("goal", ""))
        async with self._lock:
            if task_id not in self._in_flight:
                self._in_flight[task_id] = InFlightExecution(
                    task_id=task_id, goal=goal,
                )
                self._in_flight[task_id].correlation_id = event.correlation_id
                self._in_flight[task_id].input_summary = str(
                    event.payload.get("input_summary", ""),
                )
                self._in_flight[task_id].workflow_id = event.payload.get("workflow_id")

    async def _on_agent_dispatched(self, event: Event) -> None:
        """Record which agent + provider was dispatched."""
        task_id = self._extract_task_id(event)
        if task_id is None:
            return
        async with self._lock:
            if task_id not in self._in_flight:
                self._in_flight[task_id] = InFlightExecution(task_id=task_id)
            exec_state = self._in_flight[task_id]
            exec_state.agent_id = event.payload.get("agent_id", exec_state.agent_id)
            exec_state.agent_type = event.payload.get("agent_type", exec_state.agent_type)
            exec_state.provider = event.payload.get("provider", exec_state.provider)
            exec_state.model = event.payload.get("model", exec_state.model)
            capability = event.payload.get("capability")
            if capability and capability not in exec_state.capabilities_used:
                exec_state.capabilities_used.append(str(capability))

    async def _on_agent_completed(self, event: Event) -> None:
        """Record agent completion metrics."""
        task_id = self._extract_task_id(event)
        if task_id is None:
            return
        async with self._lock:
            if task_id not in self._in_flight:
                return
            exec_state = self._in_flight[task_id]
            exec_state.output_summary = str(
                event.payload.get("output_summary", exec_state.output_summary),
            )
            exec_state.cost_usd += float(event.payload.get("cost_usd", 0.0))
            exec_state.token_usage_input += int(event.payload.get("input_tokens", 0))
            exec_state.token_usage_output += int(event.payload.get("output_tokens", 0))
            exec_state.retries += int(event.payload.get("retries", 0))
            exec_state.confidence = float(
                event.payload.get("confidence", exec_state.confidence),
            )
            success = event.payload.get("success")
            if success is False:
                exec_state.success = False
                exec_state.outcome = ExperienceOutcome.FAILURE.value
                exec_state.failure_reason = str(
                    event.payload.get("error", "Agent reported failure"),
                )

    async def _on_step_started(self, event: Event) -> None:
        """Record a step starting."""
        task_id = self._extract_task_id(event)
        if task_id is None:
            return
        step_id = str(event.payload.get("step_id", ""))
        if not step_id:
            return
        step = ExecutionStep(
            step_id=step_id,
            goal=str(event.payload.get("goal", "")),
            capability=str(event.payload.get("capability", "")),
            status="running",
        )
        async with self._lock:
            if task_id not in self._in_flight:
                self._in_flight[task_id] = InFlightExecution(task_id=task_id)
            self._in_flight[task_id].add_step(step)

    async def _on_step_completed(self, event: Event) -> None:
        """Record a step completing."""
        task_id = self._extract_task_id(event)
        if task_id is None:
            return
        step_id = str(event.payload.get("step_id", ""))
        if not step_id:
            return
        async with self._lock:
            if task_id not in self._in_flight:
                return
            exec_state = self._in_flight[task_id]
            for i, step in enumerate(exec_state.plan):
                if step.step_id == step_id:
                    exec_state.plan[i] = ExecutionStep(
                        step_id=step.step_id,
                        goal=step.goal,
                        capability=step.capability,
                        agent_id=event.payload.get("agent_id", step.agent_id),
                        status=str(event.payload.get("status", "succeeded")),
                        duration_s=float(event.payload.get("duration_s", step.duration_s)),
                        retries=int(event.payload.get("retries", step.retries)),
                        error=event.payload.get("error"),
                    )
                    break

    async def _on_task_completed(self, event: Event) -> None:
        """Finalize and store the experience record."""
        task_id = self._extract_task_id(event)
        if task_id is None:
            return
        async with self._lock:
            exec_state = self._in_flight.pop(task_id, None)
        if exec_state is None:
            # No tracking started — create minimal record from event
            exec_state = InFlightExecution(task_id=task_id, goal=str(event.payload.get("goal", "")))
        exec_state.end_time = time.time()
        # Override outcome from event if present
        outcome_str = str(event.payload.get("outcome", exec_state.outcome))
        exec_state.outcome = outcome_str
        exec_state.success = bool(event.payload.get("success", exec_state.success))
        if event.payload.get("failure_reason"):
            exec_state.failure_reason = str(event.payload["failure_reason"])
        if event.payload.get("recovery_action"):
            exec_state.recovery_action = str(event.payload["recovery_action"])
        exec_state.reflection_score = float(event.payload.get("reflection_score", 0.0))
        exec_state.qa_score = float(event.payload.get("qa_score", 0.0))
        exec_state.cost_usd += float(event.payload.get("cost_usd", 0.0))

        if self._flush_on_outcome:
            await self._flush(exec_state)

    async def _on_feedback(self, event: Event) -> None:
        """Record user feedback on a completed experience."""
        # Feedback comes after the record is stored; update it
        from services.experience.models import UserFeedback
        experience_id_str = event.payload.get("experience_id")
        if not experience_id_str:
            return
        try:
            experience_id = UUID(str(experience_id_str))
        except ValueError:
            return
        feedback = UserFeedback(
            rating=int(event.payload.get("rating", 0)),
            comment=str(event.payload.get("comment", "")),
            approved=event.payload.get("approved"),
        )
        # We can't mutate a frozen record, so we create a new one with feedback
        try:
            existing = await self._store.get(experience_id)
        except Exception:
            return
        # Build a new record with the feedback applied (replace)
        from dataclasses import replace as dc_replace
        updated = dc_replace(existing, user_feedback=feedback)
        try:
            await self._store.replace(updated)
        except Exception as e:
            _log.warning("Failed to apply feedback to %s: %s", experience_id, e)

    async def _flush(self, exec_state: InFlightExecution) -> None:
        """Build an ExperienceRecord from the in-flight state and store it."""
        if exec_state.agent_id is None:
            # No agent dispatched — skip (task didn't reach execution)
            _log.debug(
                "Skipping experience flush for task %s (no agent dispatched)",
                exec_state.task_id,
            )
            return
        record = ExperienceRecord(
            task_id=exec_state.task_id,
            agent_id=exec_state.agent_id,
            agent_type=exec_state.agent_type or "custom",
            workflow_id=exec_state.workflow_id,
            correlation_id=exec_state.correlation_id,
            provider=exec_state.provider,
            model=exec_state.model,
            capabilities_used=list(exec_state.capabilities_used),
            goal=exec_state.goal,
            plan=list(exec_state.plan),
            input_summary=exec_state.input_summary,
            output_summary=exec_state.output_summary,
            execution_time_s=exec_state.execution_time_s(),
            latency_s=exec_state.execution_time_s(),
            retries=exec_state.retries,
            reflection_score=exec_state.reflection_score,
            qa_score=exec_state.qa_score,
            outcome=exec_state.outcome,
            success=exec_state.success,
            failure_reason=exec_state.failure_reason,
            recovery_action=exec_state.recovery_action,
            cost_usd=exec_state.cost_usd,
            token_usage=TokenUsage(
                input_tokens=exec_state.token_usage_input,
                output_tokens=exec_state.token_usage_output,
            ),
            confidence=exec_state.confidence,
        )
        await self._store.store(record)

    def _extract_task_id(self, event: Event) -> UUID | None:
        """Extract a task_id from an event payload or correlation_id."""
        tid = event.payload.get("task_id")
        if tid is not None:
            try:
                return UUID(str(tid))
            except (ValueError, TypeError):
                pass
        # Fall back to correlation_id
        return event.correlation_id

    async def record_manual(
        self,
        record: ExperienceRecord,
    ) -> ExperienceRecord:
        """Manually record an experience (bypass the event bus).

        Useful for tests and for replaying historical data.
        """
        return await self._store.store(record)

    async def in_flight_count(self) -> int:
        """Return the number of executions currently being tracked."""
        async with self._lock:
            return len(self._in_flight)
