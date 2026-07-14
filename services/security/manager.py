"""SecurityManager — the unified security entry point.

Wires together:
  - PolicyEngine (RBAC + ABAC)
  - EncryptedSecretStore (with rotation)
  - InMemoryAuditLog (hash-chained)

The SecurityManager implements the Gateway's PermissionChecker and
AuditLogger protocols, replacing the Phase 3 NoOp stubs.
"""

from __future__ import annotations

from typing import Any

from core.contracts.actor import ActorRef
from core.contracts.permission import Permission, PermissionDecision
from core.gateway.audit import AuditEntry, AuditLogger
from core.gateway.permission import PermissionChecker, PermissionResult
from core.logging import get_logger
from services.security.audit_log import AuditLogEntry, InMemoryAuditLog
from services.security.policy import PolicyDecision, PolicyEngine, Role
from services.security.secret_store import EncryptedSecretStore

_log = get_logger(__name__)

__all__ = [
    "SecurityManager",
    "get_security_manager",
    "init_security_manager",
    "set_security_manager",
]


class SecurityManager(PermissionChecker, AuditLogger):
    """The unified security manager.

    Implements both PermissionChecker and AuditLogger (the Gateway protocols),
    so it can be injected into the Gateway via ``set_permission_checker()``
    and ``set_audit_logger()``.
    """

    def __init__(
        self,
        *,
        policy_engine: PolicyEngine | None = None,
        secret_store: EncryptedSecretStore | None = None,
        audit_log: InMemoryAuditLog | None = None,
    ) -> None:
        self._policy: PolicyEngine = policy_engine or PolicyEngine()
        self._secrets: EncryptedSecretStore = secret_store or EncryptedSecretStore()
        self._audit: InMemoryAuditLog = audit_log or InMemoryAuditLog()

    @property
    def policy(self) -> PolicyEngine:
        """Return the policy engine."""
        return self._policy

    @property
    def secrets(self) -> EncryptedSecretStore:
        """Return the secret store."""
        return self._secrets

    @property
    def audit(self) -> InMemoryAuditLog:
        """Return the audit log."""
        return self._audit

    # ------------------------------------------------------------------
    # PermissionChecker protocol
    # ------------------------------------------------------------------

    async def check(
        self,
        actor: ActorRef,
        permission: Permission,
        *,
        resource: str | None = None,
    ) -> PermissionResult:
        """Check if ``actor`` may perform ``permission`` on ``resource``."""
        decision = self._policy.evaluate(actor, permission, resource or "*")
        if decision == PolicyDecision.ALLOW:
            return PermissionResult(decision=PermissionDecision.ALLOW)
        if decision == PolicyDecision.DENY:
            return PermissionResult(decision=PermissionDecision.DENY, reason="policy denied")
        # ASK
        return PermissionResult(decision=PermissionDecision.ASK, reason="policy requires approval")

    # ------------------------------------------------------------------
    # AuditLogger protocol
    # ------------------------------------------------------------------

    async def log(self, entry: AuditEntry) -> None:
        """Persist an audit entry."""
        audit_entry = AuditLogEntry(
            actor=entry.actor,
            action=entry.action,
            target=entry.target,
            success=entry.success,
            reason=entry.reason,
            correlation_id=entry.correlation_id,
            metadata=entry.metadata,
        )
        await self._audit.log(audit_entry)

    # ------------------------------------------------------------------
    # Role management
    # ------------------------------------------------------------------

    def assign_role(self, actor_id: str, role: Role) -> None:
        """Assign a role to an actor."""
        self._policy.assign_role(actor_id, role)

    def get_role(self, actor_id: str) -> Role | None:
        """Return an actor's role."""
        return self._policy.get_role(actor_id)

    # ------------------------------------------------------------------
    # Secret access (convenience methods)
    # ------------------------------------------------------------------

    async def get_secret(self, name: str) -> str:
        """Return the plaintext value of a secret."""
        return await self._secrets.get(name)

    async def set_secret(self, name: str, value: str) -> None:
        """Set a secret."""
        await self._secrets.set(name, value)

    async def rotate_secret(self, name: str, new_value: str) -> None:
        """Rotate a secret."""
        await self._secrets.rotate(name, new_value)

    # ------------------------------------------------------------------
    # Audit access
    # ------------------------------------------------------------------

    async def get_audit_entries(
        self,
        *,
        actor_id: str | None = None,
        action: str | None = None,
        limit: int = 100,
    ) -> list[AuditLogEntry]:
        """Return filtered audit entries."""
        return await self._audit.get_entries(
            actor_id=actor_id,
            action=action,
            limit=limit,
        )

    async def verify_audit_chain(self) -> bool:
        """Verify the audit log hash chain is intact."""
        return await self._audit.verify_chain()

    # ------------------------------------------------------------------
    # Wire into the Gateway
    # ------------------------------------------------------------------

    def install_in_gateway(self) -> None:
        """Install this SecurityManager as the Gateway's permission checker + audit logger."""
        from core.gateway import set_audit_logger, set_permission_checker

        set_permission_checker(self)
        set_audit_logger(self)
        _log.info("security.installed_in_gateway")


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_INSTANCE: SecurityManager | None = None


def init_security_manager(**kwargs: Any) -> SecurityManager:
    """Initialize the global SecurityManager."""
    global _INSTANCE
    _INSTANCE = SecurityManager(**kwargs)
    return _INSTANCE


def get_security_manager() -> SecurityManager:
    """Return the global SecurityManager."""
    if _INSTANCE is None:
        raise RuntimeError("SecurityManager not initialized. Call init_security_manager() first.")
    return _INSTANCE


def set_security_manager(mgr: SecurityManager) -> None:
    """Set the global SecurityManager (for testing)."""
    global _INSTANCE
    _INSTANCE = mgr
