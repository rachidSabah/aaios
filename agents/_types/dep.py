"""DeploymentAgent — build, push, release, rollback."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from agents._types.gen import GenericAgent


@runtime_checkable
class DeploymentAgent(GenericAgent, Protocol):
    """The Deployment agent type.

    Capabilities advertised: ``deploy.build``, ``deploy.push``,
    ``deploy.release``, ``deploy.rollback``.

    Works through the gateway (no direct shell).
    """

    async def build(self, target: str, *, env: str = "production") -> Any:  # returns BuildResult
        """Build artifacts for the target."""
        ...

    async def push(self, artifact: str, registry: str) -> Any:  # returns PushResult
        """Push an artifact to a registry."""
        ...

    async def release(
        self, version: str, *, env: str = "production"
    ) -> Any:  # returns ReleaseResult
        """Release a version to an environment."""
        ...

    async def rollback(
        self, version: str, *, env: str = "production"
    ) -> Any:  # returns RollbackResult
        """Roll back to a prior version."""
        ...
