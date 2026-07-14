"""WorkflowAgent — execute saved workflows."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from agents._types.gen import GenericAgent


@runtime_checkable
class WorkflowAgent(GenericAgent, Protocol):
    """The Workflow agent type.

    Capabilities advertised: ``workflow.run``, ``workflow.validate``.

    Wraps the Workflow Engine for cases where a user wants to invoke a
    workflow as a single "agent call" inside a larger plan.
    """

    async def run(self, workflow_id: str, inputs: dict[str, Any]) -> Any:  # returns WorkflowResult
        """Run a saved workflow with the given inputs."""
        ...

    async def validate(self, workflow_id: str) -> Any:  # returns ValidationResult
        """Validate a workflow definition without running it."""
        ...
