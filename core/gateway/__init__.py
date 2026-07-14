"""Gateway — the only package allowed to perform I/O (INV-02).

No code outside ``core/gateway/`` may import ``subprocess``, ``open``,
``httpx``, ``requests``, or ``socket``. CI enforces this with a regex ban
(see ``.github/workflows/ci.yml`` and ``tests/unit/test_phase2_structure.py``).

Sub-gateways:
  - ``gateway.fs``      — filesystem (read/write/list/delete), sandbox-scoped
  - ``gateway.shell``   — shell execution, sandboxed
  - ``gateway.net``     — HTTP/HTTPS, egress-allow-listed
  - ``gateway.process`` — subprocess spawn, sandboxed
  - ``gateway.desktop`` — keyboard/mouse input, permission-gated (DesktopAgents only)
  - ``gateway.clipboard`` — clipboard read/write, permission-gated

Every gateway call:
  1. Is permission-checked against the Security Layer.
  2. Is audit-logged (actor, action, target, timestamp, success/failure).
  3. Is rate-limited per actor.
  4. Goes through the platform adapter for OS-specific primitives.

Phase 3 implements the structure and the in-process checks. The full
Security Layer (services/security/) lands in Phase 8. Until then, the
Gateway uses a no-op permission checker and audit logger — the call still
goes through the Gateway, so the invariant (INV-02) holds.
"""

from __future__ import annotations

from core.gateway.audit import (
    AuditEntry,
    AuditLogger,
    NoOpAuditLogger,
    get_audit_logger,
    set_audit_logger,
)
from core.gateway.fs import FileSystemGateway, get_fs_gateway
from core.gateway.gateway import Gateway, get_gateway
from core.gateway.net import NetworkGateway, get_net_gateway
from core.gateway.permission import (
    NoOpPermissionChecker,
    PermissionChecker,
    PermissionResult,
    get_permission_checker,
    set_permission_checker,
)
from core.gateway.shell import ShellGateway, get_shell_gateway

__all__ = [
    "AuditEntry",
    "AuditLogger",
    "FileSystemGateway",
    "Gateway",
    "NetworkGateway",
    "NoOpAuditLogger",
    "NoOpPermissionChecker",
    "PermissionChecker",
    "PermissionResult",
    "ShellGateway",
    "get_audit_logger",
    "get_fs_gateway",
    "get_gateway",
    "get_net_gateway",
    "get_permission_checker",
    "get_shell_gateway",
    "set_audit_logger",
    "set_permission_checker",
]
