"""Security Layer — RBAC + ABAC policy engine, encrypted secrets, audit log.

This is the L2 service that enforces zero-trust security across the system.
It replaces the NoOp permission checker and audit logger in the Gateway
(Phase 3 stubs) with real implementations.

Components:
  - ``policy.py`` — the policy engine (allow/deny/ask based on RBAC + ABAC)
  - ``secret_store.py`` — encrypted secret storage with rotation
  - ``audit_log.py`` — append-only, hash-chained audit log
  - ``manager.py`` — SecurityManager (the unified entry point)

See docs/architecture/07-security-model.md for the full spec.
"""

from __future__ import annotations

from services.security.audit_log import (
    AuditLogEntry,
    HashChainedAuditLog,
    InMemoryAuditLog,
)
from services.security.manager import (
    SecurityManager,
    get_security_manager,
    init_security_manager,
    set_security_manager,
)
from services.security.policy import (
    PolicyDecision,
    PolicyEngine,
    PolicyRule,
    Role,
)
from services.security.secret_store import (
    EncryptedSecretStore,
    RotationPolicy,
    SecretNotFoundError,
    SecretStoreError,
)

__all__ = [
    "AuditLogEntry",
    "EncryptedSecretStore",
    "HashChainedAuditLog",
    "InMemoryAuditLog",
    "PolicyDecision",
    "PolicyEngine",
    "PolicyRule",
    "Role",
    "RotationPolicy",
    "SecretNotFoundError",
    "SecretStoreError",
    "SecurityManager",
    "get_security_manager",
    "init_security_manager",
    "set_security_manager",
]
