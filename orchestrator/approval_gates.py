"""Human approval gates — pause execution until a user approves.

When the Orchestrator reaches a step with an approval gate, it:
  1. Emits ``approval.requested`` on the event bus
  2. Pauses the step (status = PAUSED)
  3. Waits for an ``approval.responded`` event (or a direct call to
     ``ApprovalGateManager.respond()``)
  4. If approved: continues the step
  5. If denied: fails the step
  6. If timeout: per the gate's ``on_timeout`` policy (pause or deny)
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from core.contracts.actor import ActorRef
from core.contracts.event import Event, EventTopic
from core.contracts.timestamp import utc_now
from core.event_bus import EventBus, get_bus
from core.logging import get_logger
from orchestrator.contracts.approval_gate import ApprovalGate, GateTimeoutAction
from orchestrator.contracts.dag import Step

_log = get_logger(__name__)

__all__ = ["ApprovalDecision", "ApprovalGateManager", "PendingApproval"]


class ApprovalDecision(StrEnum):
    """The user's decision on an approval gate."""

    APPROVED = "approved"
    DENIED = "denied"
    MODIFIED = "modified"  # approved with edited args


@dataclass
class PendingApproval:
    """A pending approval gate waiting for a user response."""

    id: UUID = field(default_factory=uuid4)
    plan_id: UUID = field(default_factory=lambda: UUID(int=0))
    step_id: UUID = field(default_factory=lambda: UUID(int=0))
    gate: ApprovalGate | None = None
    step: Step | None = None
    requested_at: Any = field(default_factory=utc_now)  # datetime
    # The future that the waiting task awaits (created lazily)
    _future: asyncio.Future[ApprovalDecision] | None = field(default=None, repr=False)
    # Modified inputs (if the user edited them)
    modified_inputs: dict[str, Any] | None = None

    @property
    def future(self) -> asyncio.Future[ApprovalDecision]:
        """Return the future, creating it if necessary (in the running event loop)."""
        if self._future is None:
            self._future = asyncio.get_event_loop().create_future()
        return self._future


class ApprovalGateManager:
    """Manages pending approval gates.

    The Orchestrator calls ``request_approval()`` when it reaches a gate.
    The user (via the dashboard / CLI / API) calls ``respond()`` to approve
    or deny. The manager handles timeout enforcement.
    """

    def __init__(self, *, bus: EventBus | None = None) -> None:
        self._bus = bus or get_bus()
        self._pending: dict[UUID, PendingApproval] = {}
        self._timeout_tasks: dict[UUID, asyncio.Task[None]] = {}
        self._lock = asyncio.Lock()

    async def request_approval(
        self,
        plan_id: UUID,
        step: Step,
        gate: ApprovalGate,
    ) -> PendingApproval:
        """Request user approval for a step. Blocks until the user responds.

        Returns the PendingApproval (with the decision in ``future.result()``).
        """
        pending = PendingApproval(
            plan_id=plan_id,
            step_id=step.id,
            gate=gate,
            step=step,
        )
        async with self._lock:
            self._pending[pending.id] = pending

        # Emit approval.requested
        await self._bus.publish(
            Event(
                topic=EventTopic.APPROVAL_REQUESTED,
                correlation_id=plan_id,
                actor=ActorRef.system(),
                payload={
                    "approval_id": str(pending.id),
                    "step_id": str(step.id),
                    "step_goal": step.goal,
                    "gate_type": gate.gate_type.value,
                    "message": gate.message,
                    "timeout_s": gate.timeout_s,
                },
            ),
        )
        _log.info(
            "approval.requested",
            approval_id=str(pending.id),
            plan_id=str(plan_id),
            step_id=str(step.id),
        )

        # Start the timeout task
        self._timeout_tasks[pending.id] = asyncio.create_task(
            self._timeout_handler(pending.id, gate.timeout_s),
        )

        return pending

    async def respond(
        self,
        approval_id: UUID,
        decision: ApprovalDecision,
        *,
        modified_inputs: dict[str, Any] | None = None,
    ) -> bool:
        """Respond to a pending approval. Returns True if found.

        Args:
            approval_id: the pending approval ID.
            decision: APPROVED, DENIED, or MODIFIED.
            modified_inputs: if decision=MODIFIED, the new step inputs.
        """
        async with self._lock:
            pending = self._pending.get(approval_id)
            if pending is None:
                return False
            if pending.future.done():
                return False  # already responded (or timed out)
            pending.modified_inputs = modified_inputs
            pending.future.set_result(decision)
            # Cleanup
            self._pending.pop(approval_id, None)
            task = self._timeout_tasks.pop(approval_id, None)
            if task is not None:
                task.cancel()

        # Emit approval.responded
        await self._bus.publish(
            Event(
                topic=EventTopic.APPROVAL_RESPONDED,
                correlation_id=pending.plan_id,
                actor=ActorRef.system(),
                payload={
                    "approval_id": str(approval_id),
                    "decision": decision.value,
                },
            ),
        )
        _log.info(
            "approval.responded",
            approval_id=str(approval_id),
            decision=decision.value,
        )
        return True

    async def _timeout_handler(self, approval_id: UUID, timeout_s: int) -> None:
        """Handle approval timeout."""
        try:
            await asyncio.sleep(timeout_s)
        except asyncio.CancelledError:
            return

        async with self._lock:
            pending = self._pending.get(approval_id)
            if pending is None or pending.future.done():
                return
            assert pending.gate is not None
            if pending.gate.on_timeout == GateTimeoutAction.DENY:
                pending.future.set_result(ApprovalDecision.DENIED)
            else:
                # PAUSE: leave the future pending; the Orchestrator will
                # mark the task as paused and notify the user.
                # For Phase 5, we treat pause as "still waiting" — the
                # dashboard shows it as overdue.
                pass
            self._pending.pop(approval_id, None)

        _log.warning(
            "approval.timeout",
            approval_id=str(approval_id),
            action=pending.gate.on_timeout.value if pending.gate else "unknown",
        )

    def list_pending(self) -> list[PendingApproval]:
        """Return all pending approvals (for the dashboard)."""
        return list(self._pending.values())

    def get_pending(self, approval_id: UUID) -> PendingApproval | None:
        """Return a pending approval, or None."""
        return self._pending.get(approval_id)

    async def shutdown(self) -> None:
        """Cancel all pending approvals and timeout tasks."""
        for task in self._timeout_tasks.values():
            task.cancel()
        for task in self._timeout_tasks.values():
            try:
                await task
            except asyncio.CancelledError:
                pass
        self._timeout_tasks.clear()
        self._pending.clear()
