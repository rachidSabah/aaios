"""ExecutionHistory — tracks every step execution for learning.

This is the training data for the AdaptiveRouter and SelfImprovingPolicy.
Every time a step completes (success, failure, or cancellation), the result
is recorded here. The history is queryable by capability, agent, model,
and time range.

The history is stored in-memory by default. In production, it would be
backed by the event store (Postgres) for persistence across reboots.
"""

from __future__ import annotations

import asyncio
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from core.contracts.timestamp import utc_now
from core.logging import get_logger

_log = get_logger(__name__)

__all__ = ["ExecutionRecord", "ExecutionHistory", "ExecutionOutcome"]


class ExecutionOutcome(StrEnum):
    """The outcome of a step execution."""

    SUCCESS = "success"
    FAILURE = "failure"
    CANCELLED = "cancelled"


@dataclass
class ExecutionRecord:
    """A single execution history record."""

    step_id: UUID
    task_id: UUID
    agent_id: str
    capability: str
    model: str | None = None
    provider: str | None = None
    outcome: ExecutionOutcome = ExecutionOutcome.SUCCESS
    cost_usd: float = 0.0
    latency_ms: float = 0.0
    reflection_verdict: str = "accept"  # accept, reject, needs_correction
    qa_verdict: str = "pass"  # pass, fail
    correction_attempts: int = 0
    timestamp: datetime = field(default_factory=utc_now)
    metadata: dict[str, Any] = field(default_factory=dict)


class ExecutionHistory:
    """Tracks every step execution for learning.

    Usage:
        history = ExecutionHistory()
        history.record(ExecutionRecord(
            step_id=uuid4(), task_id=uuid4(), agent_id='coding-agent-v1',
            capability='code.read', outcome=ExecutionOutcome.SUCCESS,
            cost_usd=0.02, latency_ms=1500,
        ))

        # Query
        stats = history.get_capability_stats('code.read')
        agent_stats = history.get_agent_stats('coding-agent-v1')
    """

    def __init__(self, *, max_records: int = 100_000) -> None:
        self._records: list[ExecutionRecord] = []
        self._max_records = max_records
        self._by_capability: dict[str, list[ExecutionRecord]] = defaultdict(list)
        self._by_agent: dict[str, list[ExecutionRecord]] = defaultdict(list)
        self._lock = asyncio.Lock()

    async def record(self, record: ExecutionRecord) -> None:
        """Record an execution. Called after every step completes."""
        async with self._lock:
            self._records.append(record)
            self._by_capability[record.capability].append(record)
            self._by_agent[record.agent_id].append(record)

            # Trim if over limit
            if len(self._records) > self._max_records:
                old = self._records.pop(0)
                # Also trim from indexes
                cap_list = self._by_capability.get(old.capability, [])
                if old in cap_list:
                    cap_list.remove(old)
                agent_list = self._by_agent.get(old.agent_id, [])
                if old in agent_list:
                    agent_list.remove(old)

        _log.debug(
            "execution_history.recorded",
            step_id=str(record.step_id),
            agent=record.agent_id,
            capability=record.capability,
            outcome=record.outcome.value,
        )

    def get_capability_stats(self, capability: str, *, last_n: int = 100) -> dict[str, float]:
        """Return aggregate stats for a capability.

        Returns:
            {
                'success_rate': float (0.0-1.0),
                'avg_cost_usd': float,
                'avg_latency_ms': float,
                'p95_latency_ms': float,
                'correction_rate': float (fraction needing correction),
                'qa_pass_rate': float,
                'sample_count': int,
            }
        """
        records = self._by_capability.get(capability, [])[-last_n:]
        return self._compute_stats(records)

    def get_agent_stats(self, agent_id: str, *, last_n: int = 100) -> dict[str, float]:
        """Return aggregate stats for an agent."""
        records = self._by_agent.get(agent_id, [])[-last_n:]
        return self._compute_stats(records)

    def get_agent_capability_stats(
        self,
        agent_id: str,
        capability: str,
        *,
        last_n: int = 50,
    ) -> dict[str, float]:
        """Return stats for a specific agent handling a specific capability."""
        records = [
            r for r in self._by_agent.get(agent_id, [])[-last_n * 2 :] if r.capability == capability
        ][-last_n:]
        return self._compute_stats(records)

    def get_total_records(self) -> int:
        """Return the total number of records."""
        return len(self._records)

    def get_recent_records(self, limit: int = 50) -> list[ExecutionRecord]:
        """Return the most recent records."""
        return list(reversed(self._records[-limit:]))

    @staticmethod
    def _compute_stats(records: list[ExecutionRecord]) -> dict[str, float]:
        """Compute aggregate stats from a list of records."""
        if not records:
            return {
                "success_rate": 1.0,
                "avg_cost_usd": 0.0,
                "avg_latency_ms": 0.0,
                "p95_latency_ms": 0.0,
                "correction_rate": 0.0,
                "qa_pass_rate": 1.0,
                "sample_count": 0,
            }

        total = len(records)
        successes = sum(1 for r in records if r.outcome == ExecutionOutcome.SUCCESS)
        corrections = sum(1 for r in records if r.correction_attempts > 0)
        qa_passes = sum(1 for r in records if r.qa_verdict == "pass")
        costs = [r.cost_usd for r in records if r.cost_usd > 0]
        latencies = sorted([r.latency_ms for r in records])

        p95_idx = int(len(latencies) * 0.95)
        p95 = latencies[p95_idx] if latencies else 0.0

        return {
            "success_rate": successes / total,
            "avg_cost_usd": sum(costs) / len(costs) if costs else 0.0,
            "avg_latency_ms": sum(latencies) / len(latencies) if latencies else 0.0,
            "p95_latency_ms": p95,
            "correction_rate": corrections / total,
            "qa_pass_rate": qa_passes / total,
            "sample_count": total,
        }
