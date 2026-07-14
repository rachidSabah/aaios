"""Permission checker — the Security Layer hook.

In Phase 3 (kernel only), the Gateway uses a no-op checker that ALLOWs
everything. The real Security Layer (services/security/) lands in Phase 8
and provides a checker that consults the RBAC + ABAC policy table and the
Permission Manager (for interactive approval gates).

The Gateway never makes the policy decision itself — it delegates to the
checker. This keeps the Gateway simple and the policy swappable.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from core.contracts.actor import ActorRef
from core.contracts.permission import Permission, PermissionDecision


@dataclass
class PermissionResult:
    """The result of a permission check."""

    decision: PermissionDecision
    reason: str = ""
    approval_id: str | None = None  # present iff decision=ASK


class PermissionChecker(Protocol):
    """The interface every permission checker implements."""

    async def check(
        self,
        actor: ActorRef,
        permission: Permission,
        *,
        resource: str | None = None,
    ) -> PermissionResult:
        """Check whether ``actor`` may perform ``permission`` on ``resource``.

        Returns:
            ALLOW — proceed.
            DENY — refuse, log, return error to the caller.
            ASK — pause and surface to the user via the Permission Manager.
        """
        ...


class NoOpPermissionChecker:
    """Phase 3 default — ALLOWs everything.

    The kernel itself doesn't enforce policy; the Security Layer does.
    Until the Security Layer lands (Phase 8), this no-op keeps the Gateway
    functional for tests and bootstrap.
    """

    async def check(
        self,
        actor: ActorRef,
        permission: Permission,
        *,
        resource: str | None = None,
    ) -> PermissionResult:
        """Always allow."""
        return PermissionResult(decision=PermissionDecision.ALLOW, reason="no-op checker (Phase 3)")


# Singleton
_INSTANCE: PermissionChecker | None = None


def get_permission_checker() -> PermissionChecker:
    """Return the global permission checker."""
    if _INSTANCE is None:
        return NoOpPermissionChecker()
    return _INSTANCE


def set_permission_checker(checker: PermissionChecker) -> None:
    """Set the global permission checker (called by the Security Layer on boot)."""
    global _INSTANCE
    _INSTANCE = checker
