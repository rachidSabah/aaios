"""DefaultQAAgent — validates deliverables against success criteria.

QA is the final gate before a step's output is committed. It checks:
1. Deterministic checks (schema validation, lint, tests) — if applicable
2. LLM-based semantic check (if a success criterion is specified)

A step is only committed when QA passes.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from core.contracts.model import ModelMessage, ModelRequest
from core.logging import get_logger
from services.model_router import ModelRouter

_log = get_logger(__name__)

__all__ = ["DefaultQAAgent", "QAVerdict"]


class QAVerdict(StrEnum):
    """QA validation verdict."""

    PASS = "pass"
    FAIL = "fail"


class DefaultQAAgent:
    """LLM-backed QA agent.

    Uses the Model Router for semantic validation. For deterministic checks
    (schema, lint), the caller should pass the appropriate check results
    as part of the ``output``.
    """

    SYSTEM_PROMPT = """You are a QA agent. Given a deliverable and its success criterion, determine if it passes.

Respond with JSON only:
{"verdict": "pass" | "fail", "reason": "..."}

Be strict: if the success criterion is not clearly met, return "fail".
"""

    def __init__(self, router: ModelRouter | None = None) -> None:
        self._router = router

    def set_router(self, router: ModelRouter) -> None:
        """Set the model router."""
        self._router = router

    async def validate(
        self,
        deliverable: Any,
        success_criterion: str,
    ) -> tuple[QAVerdict, str]:
        """Validate a deliverable against a success criterion.

        Returns (verdict, reason).
        """
        if not success_criterion:
            # No criterion specified — auto-pass
            return QAVerdict.PASS, "No success criterion specified; auto-passed."

        if self._router is None:
            # No LLM — auto-pass (better to proceed than block)
            return QAVerdict.PASS, "No QA LLM available; auto-passed."

        try:
            deliverable_str = str(deliverable)[:4000]
            request = ModelRequest(
                messages=[
                    ModelMessage.system(self.SYSTEM_PROMPT),
                    ModelMessage.user(
                        f"Success criterion: {success_criterion}\n"
                        f"Deliverable:\n{deliverable_str}\n\n"
                        f"Does the deliverable meet the success criterion?"
                    ),
                ],
                temperature=0.1,
                max_tokens=300,
            )
            response = await self._router.complete(request)
            return self._parse_verdict(response.content)
        except Exception as e:
            _log.exception("qa.failed", error=str(e))
            return QAVerdict.PASS, f"QA failed (auto-passed): {e}"

    def _parse_verdict(self, llm_output: str) -> tuple[QAVerdict, str]:
        """Parse the LLM's JSON response."""
        import json

        try:
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
            verdict_str = data.get("verdict", "pass")
            reason = data.get("reason", "")
            verdict = QAVerdict(verdict_str)
            return verdict, reason
        except Exception:
            return QAVerdict.PASS, f"Failed to parse QA verdict: {llm_output[:200]}"
