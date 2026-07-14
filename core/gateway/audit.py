"""Audit logger — the Gateway's audit hook.

Every Gateway call (success or failure) produces an AuditEntry. The
Security Layer (Phase 8) provides a real AuditLogger that writes to the
hash-chained audit log. Until then, a no-op logger is used.

The Gateway never writes audit entries directly — it delegates to the
logger. This keeps the Gateway simple and the audit storage swappable.
"""

from __future__ import annotations

from datetime import datetime
from typing import Protocol

from pydantic import BaseModel, Field

from core.contracts.actor import ActorRef
from core.contracts.timestamp import utc_now


class AuditEntry(BaseModel):
    """A single audit log entry."""

    timestamp: datetime = Field(default_factory=utc_now)
    actor: ActorRef
    action: str  # e.g. 'gateway.fs.read'
    target: str  # e.g. the path / URL / command
    success: bool
    reason: str = ""
    correlation_id: str | None = None
    metadata: dict[str, str] = Field(default_factory=dict)


class AuditLogger(Protocol):
    """The interface every audit logger implements."""

    async def log(self, entry: AuditEntry) -> None:
        """Persist an audit entry. Must not raise."""
        ...


class NoOpAuditLogger:
    """Phase 3 default — discards entries (still goes through the Gateway)."""

    async def log(self, entry: AuditEntry) -> None:
        """No-op."""
        return


# Singleton
_INSTANCE: AuditLogger | None = None


def get_audit_logger() -> AuditLogger:
    """Return the global audit logger."""
    if _INSTANCE is None:
        return NoOpAuditLogger()
    return _INSTANCE


def set_audit_logger(logger: AuditLogger) -> None:
    """Set the global audit logger (called by the Security Layer on boot)."""
    global _INSTANCE
    _INSTANCE = logger
