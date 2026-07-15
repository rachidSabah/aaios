"""Multi-agent collaboration — agents delegate to each other.

In v1.0, only the supervisor dispatches to agents. In v2.0, agents can
request help from other agents via the delegation API.

Delegation flow:
1. Agent A is executing a step and needs help with capability X
2. Agent A calls context.delegate(capability=X, task=subtask)
3. The supervisor receives the delegation request
4. The supervisor selects Agent B for capability X
5. Agent B executes the subtask
6. The result is returned to Agent A
7. Agent A continues

The supervisor mediates all delegation — agents never call each other
directly. This preserves the supervision invariant (the supervisor always
knows what's happening).
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from uuid import UUID, uuid4

from core.contracts.actor import ActorRef
from core.contracts.task import TaskContext, TaskRequest, TaskResult
from core.logging import get_logger
from services.agent_registry import AgentRegistry
from supervisor.capability_selector import CapabilitySelector, NoCandidateError

_log = get_logger(__name__)

__all__ = ["DelegationRequest", "DelegationManager", "DelegationResult"]


@dataclass
class DelegationRequest:
    """A request from one agent to delegate work to another agent."""

    id: UUID = field(default_factory=uuid4)
    from_agent_id: str = ""
    to_capability: str = ""
    task_goal: str = ""
    task_context: TaskContext | None = None
    timeout_s: float = 300.0
    future: asyncio.Future[TaskResult] = field(
        default_factory=lambda: asyncio.get_event_loop().create_future()
    )


@dataclass
class DelegationResult:
    """The result of a delegation."""

    request_id: UUID
    result: TaskResult | None
    delegated_to: str | None = None
    error: str | None = None


class DelegationManager:
    """Manages agent-to-agent delegation.

    The supervisor creates a DelegationManager and passes it to agents
    via the AgentContext. Agents call `delegator.delegate()` to request
    help from another agent.

    Usage:
        delegator = DelegationManager(registry=registry, selector=selector)
        # Agent calls:
        result = await delegator.delegate(
            from_agent_id='coding-agent-v1',
            to_capability='web.search',
            task_goal='Find documentation for Pydantic v2',
            task_context=task_context,
        )
    """

    def __init__(
        self,
        registry: AgentRegistry,
        selector: CapabilitySelector,
    ) -> None:
        self._registry = registry
        self._selector = selector
        self._pending: dict[UUID, DelegationRequest] = {}
        self._lock = asyncio.Lock()

    async def delegate(
        self,
        *,
        from_agent_id: str,
        to_capability: str,
        task_goal: str,
        task_context: TaskContext | None = None,
        timeout_s: float = 300.0,
    ) -> TaskResult:
        """Delegate a subtask to another agent.

        Args:
            from_agent_id: The agent requesting delegation.
            to_capability: The capability needed.
            task_goal: What the delegated agent should do.
            task_context: Optional context for the task.
            timeout_s: Max time to wait for the result.

        Returns:
            The TaskResult from the delegated agent.

        Raises:
            NoCandidateError: If no agent can handle the capability.
            TimeoutError: If the delegation times out.
        """
        request = DelegationRequest(
            from_agent_id=from_agent_id,
            to_capability=to_capability,
            task_goal=task_goal,
            task_context=task_context,
            timeout_s=timeout_s,
        )

        async with self._lock:
            self._pending[request.id] = request

        _log.info(
            "delegation.requested",
            request_id=str(request.id),
            from_agent=from_agent_id,
            capability=to_capability,
            goal=task_goal[:100],
        )

        # Select an agent for the capability (excluding the requesting agent)
        try:
            selection = self._selector.select(to_capability)
            if selection.agent_id == from_agent_id:
                # Don't delegate to self — find another
                candidates = [c for c in selection.candidates if c.agent_id != from_agent_id]
                if not candidates:
                    raise NoCandidateError(to_capability)
                selection = type(selection)(
                    agent_id=candidates[0].agent_id,
                    score=candidates[0].track_record.get("success_rate", 0.5),
                    score_breakdown={},
                    candidates=candidates,
                )
        except NoCandidateError:
            request.future.set_exception(NoCandidateError(to_capability))
            async with self._lock:
                self._pending.pop(request.id, None)
            raise

        agent = self._registry.get(selection.agent_id)

        # Create a task request for the delegated agent
        task_request = TaskRequest(
            id=uuid4(),
            goal=task_goal,
            context=task_context or TaskContext(submitted_by=ActorRef.agent(from_agent_id)),
        )

        # Execute the delegated task
        try:
            raw_result = await asyncio.wait_for(
                agent.execute_task(task_request),  # type: ignore[attr-defined]
                timeout=timeout_s,
            )

            from core.contracts.task import TaskResult

            result = (
                TaskResult.model_validate(raw_result)
                if isinstance(raw_result, dict)
                else raw_result
            )

            _log.info(
                "delegation.completed",
                request_id=str(request.id),
                delegated_to=selection.agent_id,
                status=result.status.value,
            )

            request.future.set_result(result)
            async with self._lock:
                self._pending.pop(request.id, None)

            return result

        except TimeoutError:
            _log.warning(
                "delegation.timeout",
                request_id=str(request.id),
                timeout_s=timeout_s,
            )
            request.future.set_exception(TimeoutError(f"Delegation timed out after {timeout_s}s"))
            async with self._lock:
                self._pending.pop(request.id, None)
            raise

        except Exception as e:
            _log.exception(
                "delegation.failed",
                request_id=str(request.id),
                error=str(e),
            )
            request.future.set_exception(e)
            async with self._lock:
                self._pending.pop(request.id, None)
            raise

    def get_pending_delegations(self) -> list[DelegationRequest]:
        """Return all pending delegation requests (for dashboard)."""
        return list(self._pending.values())
