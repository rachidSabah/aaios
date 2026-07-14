"""Cost ledger — tracks per-task, per-user, per-provider cost.

All LLM costs flow through here. The dashboard reads this for the cost
analytics page. The Orchestrator reads this to enforce budget limits.
"""

from __future__ import annotations

import asyncio
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID

from core.contracts.timestamp import utc_now
from core.logging import get_logger

_log = get_logger(__name__)

__all__ = ["CostEntry", "CostLedger"]


@dataclass
class CostEntry:
    """A single cost entry."""

    task_id: UUID | None
    user_id: str | None
    provider: str
    model: str
    cost_usd: float
    prompt_tokens: int
    completion_tokens: int
    timestamp: datetime = field(default_factory=utc_now)


class CostLedger:
    """In-memory cost ledger.

    For Phase 6, entries are kept in memory. In production, they'd be
    persisted to the event store (Phase 8 with the Security Layer).
    """

    def __init__(self, *, max_entries: int = 100_000) -> None:
        self._entries: list[CostEntry] = []
        self._max_entries = max_entries
        self._total_cost: float = 0.0
        self._by_provider: dict[str, float] = defaultdict(float)
        self._by_task: dict[UUID, float] = defaultdict(float)
        self._by_user: dict[str, float] = defaultdict(float)
        self._lock = asyncio.Lock()

    async def record(
        self,
        *,
        provider: str,
        model: str,
        cost_usd: float,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        task_id: UUID | None = None,
        user_id: str | None = None,
    ) -> None:
        """Record a cost entry."""
        entry = CostEntry(
            task_id=task_id,
            user_id=user_id,
            provider=provider,
            model=model,
            cost_usd=cost_usd,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
        )
        async with self._lock:
            self._entries.append(entry)
            if len(self._entries) > self._max_entries:
                # Drop oldest
                old = self._entries.pop(0)
                self._by_provider[old.provider] -= old.cost_usd
                if old.task_id is not None:
                    self._by_task[old.task_id] -= old.cost_usd
                if old.user_id is not None:
                    self._by_user[old.user_id] -= old.cost_usd
                self._total_cost -= old.cost_usd
            self._total_cost += cost_usd
            self._by_provider[provider] += cost_usd
            if task_id is not None:
                self._by_task[task_id] += cost_usd
            if user_id is not None:
                self._by_user[user_id] += cost_usd

    def get_total_cost(self) -> float:
        """Return the total cost across all entries."""
        return self._total_cost

    def get_cost_by_provider(self, provider: str | None = None) -> dict[str, float] | float:
        """Return cost by provider (all, or a specific provider)."""
        if provider is not None:
            return self._by_provider.get(provider, 0.0)
        return dict(self._by_provider)

    def get_cost_by_task(self, task_id: UUID) -> float:
        """Return the total cost for a task."""
        return self._by_task.get(task_id, 0.0)

    def get_cost_by_user(self, user_id: str) -> float:
        """Return the total cost for a user."""
        return self._by_user.get(user_id, 0.0)

    def get_entries(
        self,
        *,
        provider: str | None = None,
        task_id: UUID | None = None,
        user_id: str | None = None,
        limit: int = 100,
    ) -> list[CostEntry]:
        """Return filtered cost entries (most recent first)."""
        result = self._entries
        if provider is not None:
            result = [e for e in result if e.provider == provider]
        if task_id is not None:
            result = [e for e in result if e.task_id == task_id]
        if user_id is not None:
            result = [e for e in result if e.user_id == user_id]
        return list(reversed(result))[:limit]
