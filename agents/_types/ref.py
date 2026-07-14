"""ReflectionAgent — critiques an agent output."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from agents._types.gen import GenericAgent


@runtime_checkable
class ReflectionAgent(GenericAgent, Protocol):
    """The Reflection agent type.

    Capabilities advertised: ``reflect.critique``.

    Pure-function agent (no side effects). Cheap model by default.
    """

    async def critique(self, step_goal: str, agent_output: Any) -> Any:  # returns CritiqueResult
        """Critique an agent's output against the step goal.

        Returns a verdict (``accept`` | ``reject`` | ``needs_correction``)
        and a critique string.
        """
        ...
