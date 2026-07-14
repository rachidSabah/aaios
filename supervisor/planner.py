"""LlmPlanner — decomposes goals into DAG plans via the Model Router.

The Planner takes a natural-language goal and produces a Plan (DAG of Steps).
Each Step has a capability requirement (NOT an agent name — INV-09).

Phase 8: uses a prompt template + the Model Router. The LLM returns a JSON
plan, which is parsed into a Plan object.
"""

from __future__ import annotations

import json
from typing import Any
from uuid import UUID, uuid4

from core.contracts.model import ModelMessage, ModelRequest
from core.contracts.model.request import RequestHint
from core.logging import get_logger
from orchestrator.contracts.dag import Plan, Step
from orchestrator.contracts.retry import RetryPolicy
from services.model_router import ModelRouter

_log = get_logger(__name__)

__all__ = ["LlmPlanner", "PlanResult"]


class PlanResult:
    """The result of planning."""

    def __init__(self, plan: Plan, reasoning: str = "") -> None:
        self.plan = plan
        self.reasoning = reasoning


class LlmPlanner:
    """LLM-backed planner.

    Usage:
        planner = LlmPlanner(router=get_model_router())
        result = await planner.decompose('refactor auth module', task_id)
        plan = result.plan  # a Plan with steps
    """

    # The system prompt for planning
    SYSTEM_PROMPT = """You are an AI task planner. Given a goal, decompose it into a DAG of steps.

Each step must have:
- "goal": what the step accomplishes (natural language)
- "capability": the capability namespace (e.g. "code.read", "code.write", "test.run", "desktop.ui.click", "web.search")
- "depends_on": list of step names that must complete first (empty for root steps)
- "name": a short unique name for this step (used by dependents)

Respond with JSON only:
{"steps": [{"name": "s1", "goal": "...", "capability": "...", "depends_on": []}, ...]}

Rules:
- Keep plans small (2-8 steps)
- Each capability must be a dot-separated namespace
- Dependencies must reference prior step names
- No cycles
"""

    def __init__(self, router: ModelRouter | None = None) -> None:
        self._router = router

    def set_router(self, router: ModelRouter) -> None:
        """Set the model router (called after init_model_router)."""
        self._router = router

    async def decompose(
        self,
        goal: str,
        task_id: UUID,
        *,
        context: dict[str, Any] | None = None,
    ) -> PlanResult:
        """Decompose a goal into a Plan.

        If no router is available (or the LLM call fails), falls back to a
        single-step plan (the goal itself as one step with capability 'plan.decompose').
        """
        if self._router is None:
            _log.warning("planner.no_router", msg="Falling back to single-step plan")
            return self._fallback_plan(goal, task_id)

        try:
            return await self._llm_decompose(goal, task_id, context or {})
        except Exception as e:
            _log.exception("planner.llm_failed", error=str(e))
            return self._fallback_plan(goal, task_id)

    async def _llm_decompose(
        self,
        goal: str,
        task_id: UUID,
        context: dict[str, Any],
    ) -> PlanResult:
        """Call the LLM to decompose the goal."""
        assert self._router is not None
        request = ModelRequest(
            messages=[
                ModelMessage.system(self.SYSTEM_PROMPT),
                ModelMessage.user(f"Goal: {goal}\n\nDecompose into steps."),
            ],
            hints={RequestHint.SMART},
            temperature=0.3,
            max_tokens=2000,
        )
        response = await self._router.complete(request)
        plan = self._parse_plan(response.content, task_id)
        return PlanResult(plan=plan, reasoning=response.content)

    def _parse_plan(self, llm_output: str, task_id: UUID) -> Plan:
        """Parse the LLM's JSON output into a Plan object."""
        # Try to extract JSON from the output (the LLM might add markdown fences)
        json_str = llm_output.strip()
        if "```json" in json_str:
            start = json_str.index("```json") + 7
            end = json_str.index("```", start)
            json_str = json_str[start:end].strip()
        elif "```" in json_str:
            start = json_str.index("```") + 3
            end = json_str.index("```", start)
            json_str = json_str[start:end].strip()

        data = json.loads(json_str)
        steps_data = data.get("steps", [])

        # First pass: assign UUIDs and build name→UUID map
        name_to_id: dict[str, UUID] = {}
        for step_data in steps_data:
            name = step_data.get("name", f"step-{len(name_to_id)}")
            name_to_id[name] = uuid4()

        # Second pass: build Step objects
        steps: list[Step] = []
        for step_data in steps_data:
            name = step_data.get("name", f"step-{len(steps)}")
            dep_names = step_data.get("depends_on", [])
            dep_ids = [name_to_id[n] for n in dep_names if n in name_to_id]
            steps.append(
                Step(
                    id=name_to_id[name],
                    goal=step_data.get("goal", name),
                    capability=step_data["capability"],
                    depends_on=dep_ids,
                    retry_policy=RetryPolicy(),
                )
            )

        return Plan(id=uuid4(), task_id=task_id, steps=steps)

    def _fallback_plan(self, goal: str, task_id: UUID) -> PlanResult:
        """Create a single-step plan (fallback when no LLM is available)."""
        step = Step(
            id=uuid4(),
            goal=goal,
            capability="plan.decompose",
            depends_on=[],
            retry_policy=RetryPolicy(),
        )
        plan = Plan(id=uuid4(), task_id=task_id, steps=[step])
        return PlanResult(plan=plan, reasoning="Fallback: single-step plan (no LLM available)")
