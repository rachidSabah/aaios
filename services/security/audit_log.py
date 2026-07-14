"""Audit log — append-only, hash-chained.

Every security-relevant action is logged here. The log is tamper-evident:
each entry's hash includes the previous entry's hash, so any modification
is detectable by recomputing the chain.

See docs/architecture/07-security-model.md §6.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
from typing import Any

from core.contracts.actor import ActorRef
from core.contracts.timestamp import utc_now
from core.logging import get_logger

_log = get_logger(__name__)

__all__ = ["AuditLogEntry", "HashChainedAuditLog", "InMemoryAuditLog"]


class AuditLogEntry:
    """A single audit log entry."""

    def __init__(
        self,
        actor: ActorRef,
        action: str,
        target: str,
        success: bool,
        reason: str = "",
        correlation_id: str | None = None,
        metadata: dict[str, str] | None = None,
    ) -> None:
        self.timestamp = utc_now()
        self.actor = actor
        self.action = action
        self.target = target
        self.success = success
        self.reason = reason
        self.correlation_id = correlation_id
        self.metadata = metadata or {}
        self.previous_hash: str = ""
        self.hash: str = ""

    def compute_hash(self, previous_hash: str) -> str:
        """Compute the hash of this entry, including the previous entry's hash."""
        self.previous_hash = previous_hash
        data = json.dumps(
            {
                "timestamp": self.timestamp.isoformat(),
                "actor": str(self.actor),
                "action": self.action,
                "target": self.target,
                "success": self.success,
                "reason": self.reason,
                "correlation_id": self.correlation_id,
                "metadata": self.metadata,
                "previous_hash": self.previous_hash,
            },
            sort_keys=True,
        )
        return hashlib.sha256(data.encode()).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a dict."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "actor": str(self.actor),
            "action": self.action,
            "target": self.target,
            "success": self.success,
            "reason": self.reason,
            "correlation_id": self.correlation_id,
            "metadata": self.metadata,
            "previous_hash": self.previous_hash,
            "hash": self.hash,
        }


class InMemoryAuditLog:
    """In-memory audit log with hash chaining.

    The hash chain ensures tamper-evidence: each entry's hash includes the
    previous entry's hash. Any modification is detectable by recomputing
    the chain.
    """

    def __init__(self) -> None:
        self._entries: list[AuditLogEntry] = []
        self._genesis_hash = hashlib.sha256(b"aaios-audit-genesis").hexdigest()
        self._lock = asyncio.Lock()

    async def log(self, entry: AuditLogEntry) -> None:
        """Append an entry to the log. Computes the hash chain."""
        async with self._lock:
            previous_hash = self._entries[-1].hash if self._entries else self._genesis_hash
            entry.hash = entry.compute_hash(previous_hash)
            self._entries.append(entry)

    async def get_entries(
        self,
        *,
        actor_id: str | None = None,
        action: str | None = None,
        limit: int = 100,
    ) -> list[AuditLogEntry]:
        """Return filtered entries (most recent first)."""
        async with self._lock:
            result = list(reversed(self._entries))
            if actor_id is not None:
                result = [e for e in result if e.actor.id == actor_id]
            if action is not None:
                result = [e for e in result if e.action == action]
            return result[:limit]

    async def verify_chain(self) -> bool:
        """Verify the hash chain is intact. Returns True if valid."""
        async with self._lock:
            expected_hash = self._genesis_hash
            for entry in self._entries:
                computed = entry.compute_hash(expected_hash)
                if computed != entry.hash:
                    _log.error(
                        "audit.chain_broken", entry_action=entry.action, entry_target=entry.target
                    )
                    return False
                expected_hash = entry.hash
            return True

    async def count(self) -> int:
        """Return the total entry count."""
        async with self._lock:
            return len(self._entries)

    async def export(self) -> list[dict[str, Any]]:
        """Export all entries as dicts (for backup)."""
        async with self._lock:
            return [e.to_dict() for e in self._entries]


# Type alias — the hash-chained implementation is the default
HashChainedAuditLog = InMemoryAuditLog
