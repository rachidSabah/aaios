"""Experience Replayer — replay past experiences to extract lessons.

Replay modes:
  - dry_run: simulate the execution, return what would happen
  - re_execute: actually re-run the task with the recorded agent/provider
  - compare: re-run with a different agent and compare results

Useful for:
  - Validating that fixes work
  - Comparing agents on identical inputs
  - Generating training data
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from core.logging import get_logger
from services.experience.store import ExperienceStore

_log = get_logger(__name__)

__all__ = ["ReplayMode", "ReplayResult", "ExperienceReplayer"]


class ReplayMode:
    """Replay modes."""

    DRY_RUN = "dry_run"
    RE_EXECUTE = "re_execute"
    COMPARE = "compare"


@dataclass
class ReplayResult:
    """Result of replaying an experience."""

    original_experience_id: UUID
    mode: str
    started_at: str = ""
    finished_at: str = ""
    new_experience_id: UUID | None = None
    new_agent_id: str | None = None
    new_outcome: str | None = None
    new_execution_time_s: float = 0.0
    new_cost_usd: float = 0.0
    comparison: dict[str, Any] | None = None
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "original_experience_id": str(self.original_experience_id),
            "mode": self.mode,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "new_experience_id": str(self.new_experience_id) if self.new_experience_id else None,
            "new_agent_id": self.new_agent_id,
            "new_outcome": self.new_outcome,
            "new_execution_time_s": self.new_execution_time_s,
            "new_cost_usd": self.new_cost_usd,
            "comparison": self.comparison,
            "error": self.error,
        }


class ExperienceReplayer:
    """Replays past experiences.

    In dry_run mode, returns the original record's outcome without re-executing.
    In re_execute mode, requires an executor callable that takes (agent_id,
    goal, input_summary) and returns a new ExperienceRecord. In compare mode,
    runs both the original agent and a comparison agent.
    """

    def __init__(
        self,
        store: ExperienceStore,
        *,
        executor: Any | None = None,
    ) -> None:
        self._store = store
        self._executor = executor

    async def replay(
        self,
        experience_id: UUID,
        *,
        mode: str = ReplayMode.DRY_RUN,
        comparison_agent_id: str | None = None,
    ) -> ReplayResult:
        """Replay a single experience."""
        started = datetime.now(UTC)
        try:
            original = await self._store.get(experience_id)
        except Exception as e:
            return ReplayResult(
                original_experience_id=experience_id,
                mode=mode,
                started_at=started.isoformat(),
                finished_at=datetime.now(UTC).isoformat(),
                error=f"Original experience not found: {e}",
            )

        if mode == ReplayMode.DRY_RUN:
            return ReplayResult(
                original_experience_id=experience_id,
                mode=mode,
                started_at=started.isoformat(),
                finished_at=datetime.now(UTC).isoformat(),
                new_agent_id=original.agent_id,
                new_outcome=original.outcome,
                new_execution_time_s=original.execution_time_s,
                new_cost_usd=original.cost_usd,
                comparison={
                    "original_outcome": original.outcome,
                    "expected_outcome": original.outcome,
                    "match": True,
                },
            )

        if mode == ReplayMode.RE_EXECUTE:
            if self._executor is None:
                return ReplayResult(
                    original_experience_id=experience_id,
                    mode=mode,
                    started_at=started.isoformat(),
                    finished_at=datetime.now(UTC).isoformat(),
                    error="No executor configured for re-execution",
                )
            try:
                new_record = await self._executor(
                    agent_id=original.agent_id,
                    goal=original.goal,
                    input_summary=original.input_summary,
                    capabilities_used=original.capabilities_used,
                )
                await self._store.store(new_record)
                return ReplayResult(
                    original_experience_id=experience_id,
                    mode=mode,
                    started_at=started.isoformat(),
                    finished_at=datetime.now(UTC).isoformat(),
                    new_experience_id=new_record.experience_id,
                    new_agent_id=new_record.agent_id,
                    new_outcome=new_record.outcome,
                    new_execution_time_s=new_record.execution_time_s,
                    new_cost_usd=new_record.cost_usd,
                    comparison={
                        "original_outcome": original.outcome,
                        "new_outcome": new_record.outcome,
                        "match": original.outcome == new_record.outcome,
                        "time_delta_s": new_record.execution_time_s - original.execution_time_s,
                        "cost_delta_usd": new_record.cost_usd - original.cost_usd,
                    },
                )
            except Exception as e:
                return ReplayResult(
                    original_experience_id=experience_id,
                    mode=mode,
                    started_at=started.isoformat(),
                    finished_at=datetime.now(UTC).isoformat(),
                    error=f"Re-execution failed: {e}",
                )

        if mode == ReplayMode.COMPARE:
            if not comparison_agent_id:
                return ReplayResult(
                    original_experience_id=experience_id,
                    mode=mode,
                    started_at=started.isoformat(),
                    finished_at=datetime.now(UTC).isoformat(),
                    error="compare mode requires comparison_agent_id",
                )
            if self._executor is None:
                return ReplayResult(
                    original_experience_id=experience_id,
                    mode=mode,
                    started_at=started.isoformat(),
                    finished_at=datetime.now(UTC).isoformat(),
                    error="No executor configured for comparison",
                )
            try:
                new_record = await self._executor(
                    agent_id=comparison_agent_id,
                    goal=original.goal,
                    input_summary=original.input_summary,
                    capabilities_used=original.capabilities_used,
                )
                await self._store.store(new_record)
                return ReplayResult(
                    original_experience_id=experience_id,
                    mode=mode,
                    started_at=started.isoformat(),
                    finished_at=datetime.now(UTC).isoformat(),
                    new_experience_id=new_record.experience_id,
                    new_agent_id=new_record.agent_id,
                    new_outcome=new_record.outcome,
                    new_execution_time_s=new_record.execution_time_s,
                    new_cost_usd=new_record.cost_usd,
                    comparison={
                        "original_agent_id": original.agent_id,
                        "comparison_agent_id": comparison_agent_id,
                        "original_outcome": original.outcome,
                        "comparison_outcome": new_record.outcome,
                        "original_quality": original.quality_score(),
                        "comparison_quality": new_record.quality_score(),
                        "original_cost_usd": original.cost_usd,
                        "comparison_cost_usd": new_record.cost_usd,
                        "winner": (
                            "comparison"
                            if new_record.quality_score() > original.quality_score()
                            else "original"
                        ),
                    },
                )
            except Exception as e:
                return ReplayResult(
                    original_experience_id=experience_id,
                    mode=mode,
                    started_at=started.isoformat(),
                    finished_at=datetime.now(UTC).isoformat(),
                    error=f"Comparison failed: {e}",
                )

        return ReplayResult(
            original_experience_id=experience_id,
            mode=mode,
            started_at=started.isoformat(),
            finished_at=datetime.now(UTC).isoformat(),
            error=f"Unknown replay mode: {mode}",
        )
