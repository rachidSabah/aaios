"""PlannerAgent — decomposes a goal into a DAG plan of steps."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from agents._types.gen import GenericAgent


@runtime_checkable
class PlannerAgent(GenericAgent, Protocol):
    """The Planner agent type.

    Capabilities advertised: ``plan.decompose``, ``plan.revise``.
    """

    async def decompose(self, goal: str, context: Any) -> Any:  # returns Plan
        """Decompose a natural-language goal into a DAG of steps.

        Each step has: a goal, a capability requirement (not an agent name),
        a success criterion, a rollback hint, dependencies, and an optional
        approval gate.
        """
        ...

    async def revise(self, plan: Any, feedback: str) -> Any:  # returns Plan
        """Revise a plan mid-execution based on feedback from Reflection/QA."""
        ...
