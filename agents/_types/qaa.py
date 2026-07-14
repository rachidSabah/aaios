"""QAAgent — validates deliverables."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from agents._types.gen import GenericAgent


@runtime_checkable
class QAAgent(GenericAgent, Protocol):
    """The QA agent type.

    Capabilities advertised: ``qa.validate``, ``qa.lint``, ``qa.test``,
    ``qa.schema``.

    Deterministic where possible (lint, tests, schema validation),
    LLM-based where necessary (semantic correctness, tone, completeness).
    """

    async def validate(
        self, deliverable: Any, success_criterion: str
    ) -> Any:  # returns ValidationResult
        """Validate a deliverable against a success criterion."""
        ...

    async def lint(self, code: str, language: str = "python") -> Any:  # returns LintResult
        """Lint code. Returns issues + fix suggestions."""
        ...

    async def test(self, scope: str | None = None) -> Any:  # returns TestResult
        """Run tests in the given scope."""
        ...

    async def schema(self, data: Any, schema: dict[str, Any]) -> Any:  # returns SchemaResult
        """Validate data against a JSON Schema."""
        ...
