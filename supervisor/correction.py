"""DefaultSelfCorrectionAgent — repairs rejected outputs.

When Reflection returns REJECT or NEEDS_CORRECTION, the Self-Correction Agent
generates a repair plan: modified inputs or a modified approach for the
failing agent. It uses the critique, the original input, and the original output.

Rate-limited: max 3 correction attempts per step (configurable). After that,
the task is paused and the user is notified.
"""

from __future__ import annotations

from typing import Any

from core.contracts.model import ModelMessage, ModelRequest
from core.logging import get_logger
from services.model_router import ModelRouter

_log = get_logger(__name__)

__all__ = ["DefaultSelfCorrectionAgent"]


class DefaultSelfCorrectionAgent:
    """LLM-backed self-correction agent.

    Given the original step goal, the agent's output, and the reflection
    critique, produces a corrected output or modified instructions.
    """

    SYSTEM_PROMPT = """You are a self-correction agent. Given a step goal, the original output, and a critique, produce a corrected output.

Respond with the corrected output directly (no JSON wrapping, no explanation).
The output should be the same format as the original, but with the issues fixed.
"""

    def __init__(self, router: ModelRouter | None = None) -> None:
        self._router = router
        self._max_attempts = 3
        self._attempts: dict[str, int] = {}  # step_id → attempt count

    def set_router(self, router: ModelRouter) -> None:
        """Set the model router."""
        self._router = router

    def can_retry(self, step_id: str) -> bool:
        """Return True if the step hasn't exceeded the max correction attempts."""
        return self._attempts.get(step_id, 0) < self._max_attempts

    def reset_attempts(self, step_id: str) -> None:
        """Reset the attempt counter for a step (on success)."""
        self._attempts.pop(step_id, None)

    async def correct(
        self,
        step_goal: str,
        original_output: Any,
        critique: str,
        step_id: str = "",
    ) -> str:
        """Produce a corrected output.

        Returns the corrected output as a string.
        """
        # Track attempts
        if step_id:
            self._attempts[step_id] = self._attempts.get(step_id, 0) + 1

        if self._router is None:
            _log.warning("correction.no_router")
            return str(original_output)  # return as-is

        try:
            output_str = str(original_output)[:4000]
            request = ModelRequest(
                messages=[
                    ModelMessage.system(self.SYSTEM_PROMPT),
                    ModelMessage.user(
                        f"Step goal: {step_goal}\n"
                        f"Original output:\n{output_str}\n\n"
                        f"Critique: {critique}\n\n"
                        f"Produce the corrected output."
                    ),
                ],
                temperature=0.3,
                max_tokens=2000,
            )
            response = await self._router.complete(request)
            _log.info(
                "correction.applied",
                step_id=step_id,
                attempt=self._attempts.get(step_id, 0),
            )
            return response.content
        except Exception as e:
            _log.exception("correction.failed", error=str(e))
            return str(original_output)
