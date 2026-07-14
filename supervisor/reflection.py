"""DefaultReflectionAgent — critiques agent outputs.

After every agent execution, the Reflection Agent inspects the output and
asks: "Did this step actually move us toward the goal? Did it violate any
constraint? Is the output internally consistent?"

Returns a verdict: ACCEPT, REJECT, or NEEDS_CORRECTION, plus a critique string.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from core.contracts.model import ModelMessage, ModelRequest
from core.logging import get_logger
from services.model_router import ModelRouter

_log = get_logger(__name__)

__all__ = ["DefaultReflectionAgent", "ReflectionVerdict"]


class ReflectionVerdict(StrEnum):
    """The reflection verdict."""

    ACCEPT = "accept"
    REJECT = "reject"
    NEEDS_CORRECTION = "needs_correction"


class DefaultReflectionAgent:
    """LLM-backed reflection agent.

    Uses a cheap/fast model by default (the Router picks based on the hint).
    """

    SYSTEM_PROMPT = """You are a reflection agent. Given a step goal and the agent's output, evaluate:
1. Did the output accomplish the goal?
2. Is the output internally consistent?
3. Are there any obvious errors or missing parts?

Respond with JSON only:
{"verdict": "accept" | "reject" | "needs_correction", "critique": "..."}

Be strict but fair. "accept" means the output is good enough to proceed.
"reject" means the output is fundamentally wrong.
"needs_correction" means the output is mostly right but needs minor fixes.
"""

    def __init__(self, router: ModelRouter | None = None) -> None:
        self._router = router

    def set_router(self, router: ModelRouter) -> None:
        """Set the model router."""
        self._router = router

    async def critique(
        self,
        step_goal: str,
        agent_output: Any,
        success_criterion: str = "",
    ) -> tuple[ReflectionVerdict, str]:
        """Critique an agent's output.

        Returns (verdict, critique_string).
        """
        if self._router is None:
            # No LLM — accept everything (the QA agent will catch real issues)
            return ReflectionVerdict.ACCEPT, "No reflection LLM available; auto-accepted."

        try:
            output_str = str(agent_output)[:4000]  # truncate for the prompt
            request = ModelRequest(
                messages=[
                    ModelMessage.system(self.SYSTEM_PROMPT),
                    ModelMessage.user(
                        f"Step goal: {step_goal}\n"
                        f"Success criterion: {success_criterion or 'not specified'}\n"
                        f"Agent output:\n{output_str}\n\n"
                        f"Evaluate the output."
                    ),
                ],
                temperature=0.2,
                max_tokens=500,
            )
            response = await self._router.complete(request)
            return self._parse_verdict(response.content)
        except Exception as e:
            _log.exception("reflection.failed", error=str(e))
            return ReflectionVerdict.ACCEPT, f"Reflection failed: {e}"

    def _parse_verdict(self, llm_output: str) -> tuple[ReflectionVerdict, str]:
        """Parse the LLM's JSON response."""
        import json

        try:
            # Strip markdown fences if present
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
            verdict_str = data.get("verdict", "accept")
            critique = data.get("critique", "")
            verdict = ReflectionVerdict(verdict_str)
            return verdict, critique
        except Exception:
            # If parsing fails, accept (don't block on a parse error)
            return ReflectionVerdict.ACCEPT, f"Failed to parse reflection: {llm_output[:200]}"
