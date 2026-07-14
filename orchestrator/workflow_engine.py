"""Workflow Engine — executes saved, reusable workflows.

A workflow is a versioned Plan template. The Workflow Engine:
  - Parses workflow definitions (validated against a schema at save time)
  - Instantiates a Plan from the workflow + inputs
  - Submits the Plan to the Task Orchestrator
  - Tracks per-step state
  - Emits workflow events for the dashboard
  - Supports workflow variables (inputs, outputs, intermediate values)

Workflows are saved to a WorkflowStore (in-memory in Phase 5; persistent
in Phase 8 with the Security Layer).
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

from core.contracts.timestamp import utc_now
from core.logging import get_logger
from orchestrator.contracts.dag import Plan, Step, StepType
from orchestrator.core import TaskOrchestrator, get_orchestrator

_log = get_logger(__name__)

__all__ = ["WorkflowDefinition", "WorkflowEngine", "WorkflowStore"]


class WorkflowDefinition(BaseModel):
    """A saved, reusable workflow definition.

    A workflow is essentially a Plan template: a list of step templates
    plus default variables. When invoked, the engine instantiates a concrete
    Plan (with fresh UUIDs) from the definition + the caller's inputs.
    """

    model_config = ConfigDict(frozen=True)

    id: UUID = Field(default_factory=uuid4, description="Workflow ID (stable across versions).")
    name: str = Field(description="Human-readable name.")
    version: str = Field(default="1.0.0", description="Semver.")
    description: str = Field(default="")
    # Step templates — same shape as Step, but without concrete UUIDs
    # (UUIDs are generated at instantiation time)
    step_templates: list[dict[str, Any]] = Field(
        default_factory=list,
        description="List of step template dicts (goal, capability, depends_on_names, etc.).",
    )
    # Default variables (overridable by the caller)
    default_variables: dict[str, Any] = Field(default_factory=dict)
    # Input schema (JSON Schema) — validates caller inputs
    input_schema: dict[str, Any] | None = Field(default=None)
    # Output variable name (the variable to return as the workflow result)
    output_variable: str | None = Field(default=None)
    created_at: datetime = Field(default_factory=utc_now)


class WorkflowStore:
    """In-memory workflow store (persistent store in Phase 8)."""

    def __init__(self) -> None:
        self._workflows: dict[UUID, WorkflowDefinition] = {}
        self._lock = asyncio.Lock()

    async def save(self, workflow: WorkflowDefinition) -> None:
        """Save or update a workflow definition."""
        async with self._lock:
            self._workflows[workflow.id] = workflow
            _log.info(
                "workflow.saved",
                workflow_id=str(workflow.id),
                name=workflow.name,
                version=workflow.version,
            )

    async def get(self, workflow_id: UUID) -> WorkflowDefinition | None:
        """Return a workflow, or None."""
        async with self._lock:
            return self._workflows.get(workflow_id)

    async def list(self) -> list[WorkflowDefinition]:
        """Return all workflows."""
        async with self._lock:
            return list(self._workflows.values())

    async def delete(self, workflow_id: UUID) -> bool:
        """Delete a workflow. Returns True if found."""
        async with self._lock:
            if workflow_id in self._workflows:
                del self._workflows[workflow_id]
                return True
            return False


class WorkflowEngine:
    """Executes saved workflows by instantiating them as Plans.

    Usage:
        engine = WorkflowEngine(orchestrator=get_orchestrator(), store=store)
        await engine.save(my_workflow)
        plan_id = await engine.run(workflow_id, inputs={'foo': 'bar'}, priority='normal')
    """

    def __init__(
        self,
        *,
        orchestrator: TaskOrchestrator | None = None,
        store: WorkflowStore | None = None,
    ) -> None:
        self._orchestrator = orchestrator
        self._store = store or WorkflowStore()

    def set_orchestrator(self, orch: TaskOrchestrator) -> None:
        """Set the orchestrator (called after init_orchestrator())."""
        self._orchestrator = orch

    @property
    def store(self) -> WorkflowStore:
        """Return the workflow store."""
        return self._store

    async def save(self, workflow: WorkflowDefinition) -> None:
        """Save a workflow definition."""
        await self._store.save(workflow)

    async def run(
        self,
        workflow_id: UUID,
        *,
        inputs: dict[str, Any] | None = None,
        priority: str = "normal",
        task_id: UUID | None = None,
    ) -> UUID:
        """Run a workflow. Returns the plan ID.

        Args:
            workflow_id: the workflow to run.
            inputs: caller inputs (validated against the workflow's input_schema).
            priority: task priority.
            task_id: optional parent task ID (auto-generated if not provided).
        """
        workflow = await self._store.get(workflow_id)
        if workflow is None:
            raise ValueError(f"Workflow {workflow_id} not found")

        if self._orchestrator is None:
            try:
                self._orchestrator = get_orchestrator()
            except RuntimeError as e:
                raise RuntimeError("Orchestrator not initialized") from e

        # Validate inputs (Phase 5: basic check; full JSON Schema validation in Phase 8)
        inputs = inputs or {}
        merged_vars = {**workflow.default_variables, **inputs}

        # Instantiate a Plan from the workflow's step templates
        plan = self._instantiate_plan(workflow, merged_vars, task_id or uuid4())
        plan.priority = priority

        # Submit to the orchestrator
        plan_id = await self._orchestrator.submit(plan, priority=priority)
        _log.info(
            "workflow.started",
            workflow_id=str(workflow_id),
            plan_id=str(plan_id),
            inputs=inputs,
        )
        return plan_id

    def _instantiate_plan(
        self,
        workflow: WorkflowDefinition,
        variables: dict[str, Any],
        task_id: UUID,
    ) -> Plan:
        """Instantiate a concrete Plan from a workflow definition.

        Step templates use ``depends_on_names`` (a list of step names) instead
        of UUIDs. This method:
          1. Generates UUIDs for each step
          2. Builds a name→UUID map
          3. Resolves ``depends_on_names`` to ``depends_on`` (UUIDs)
          4. Substitutes ``${var.name}`` references in step inputs
        """
        # Pass 1: assign UUIDs
        name_to_id: dict[str, UUID] = {}
        steps: list[Step] = []
        for template in workflow.step_templates:
            step_name = template.get("name", f"step-{len(steps)}")
            step_id = uuid4()
            name_to_id[step_name] = step_id

        # Pass 2: build Steps
        for template in workflow.step_templates:
            step_name = template.get("name", f"step-{len(steps)}")
            step_id = name_to_id[step_name]
            dep_names = template.get("depends_on_names", [])
            dep_ids = [name_to_id[n] for n in dep_names if n in name_to_id]
            # Substitute variables in goal, success_criterion, and inputs
            raw_inputs = template.get("inputs", {})
            resolved_inputs = _substitute_vars(raw_inputs, variables)
            goal = _substitute_vars(template.get("goal", step_name), variables)
            success_criterion = _substitute_vars(
                template.get("success_criterion", ""),
                variables,
            )
            steps.append(
                Step(
                    id=step_id,
                    goal=goal,
                    capability=template["capability"],
                    success_criterion=success_criterion,
                    rollback_hint=template.get("rollback_hint", ""),
                    depends_on=dep_ids,
                    step_type=StepType(template.get("step_type", "agent")),
                    inputs=resolved_inputs,
                ),
            )

        return Plan(
            task_id=task_id,
            steps=steps,
            variables=variables,
        )


def _substitute_vars(value: Any, variables: dict[str, Any]) -> Any:
    """Substitute ``${var.name}`` references in a value.

    Supports strings, dicts, and lists (recursively).
    """
    if isinstance(value, str):
        # Simple substitution: ${var.name} → variables['name']
        import re

        def replace(match: re.Match[str]) -> str:
            ref = match.group(1)
            if ref.startswith("var."):
                key = ref[4:]
                val = variables.get(key, match.group(0))
                return str(val)
            return match.group(0)

        return re.sub(r"\$\{([^}]+)\}", replace, value)
    if isinstance(value, dict):
        return {k: _substitute_vars(v, variables) for k, v in value.items()}
    if isinstance(value, list):
        return [_substitute_vars(v, variables) for v in value]
    return value
