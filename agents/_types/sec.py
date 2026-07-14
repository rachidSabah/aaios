"""SecurityAgent — security analysis."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from agents._types.gen import GenericAgent


@runtime_checkable
class SecurityAgent(GenericAgent, Protocol):
    """The Security agent type.

    Capabilities advertised: ``security.scan``, ``security.audit``,
    ``security.review``.

    Distinct from the Security Layer (which is infrastructure); the Security
    Agent is a callable specialist.
    """

    async def scan(self, target: str, *, scanner: str = "auto") -> Any:  # returns ScanResult
        """Scan code/configs for vulnerabilities."""
        ...

    async def audit(self, target: str) -> Any:  # returns AuditResult
        """Audit permissions, configs, and access controls."""
        ...

    async def review(self, target: str) -> Any:  # returns ReviewResult
        """Review a system design or implementation for security issues."""
        ...
