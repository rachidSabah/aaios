"""Mission Persistence + Recovery + Replay + History.

Persistence: saves mission state to disk as JSON snapshots.
Recovery: restores mission state from the latest snapshot after crash.
Replay: replays mission events to reconstruct state.
History: tracks all state changes for audit + analytics.
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from core.logging import get_logger
from services.organization.models import Mission, MissionStatus
from services.organization.state_machine import (
    MissionStateMachine,
)

_log = get_logger(__name__)

__all__ = [
    "HistoryEntry",
    "MissionHistory",
    "MissionPersistence",
    "MissionRecovery",
    "MissionReplay",
    "ReplayResult",
]


@dataclass
class HistoryEntry:
    """A single entry in mission history."""

    entry_id: str = field(default_factory=lambda: f"{datetime.now(UTC).timestamp():.0f}")
    mission_id: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    event_type: str = ""  # state_change, decision, wbs_update, etc.
    description: str = ""
    data: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "entry_id": self.entry_id,
            "mission_id": self.mission_id,
            "timestamp": self.timestamp.isoformat(),
            "event_type": self.event_type,
            "description": self.description,
            "data": dict(self.data),
        }


class MissionHistory:
    """Tracks all state changes for a mission (in-memory audit log)."""

    def __init__(self) -> None:
        self._entries: list[HistoryEntry] = []
        self._lock = asyncio.Lock()

    async def add(self, entry: HistoryEntry) -> None:
        async with self._lock:
            self._entries.append(entry)

    async def get_history(
        self,
        mission_id: str | None = None,
        *,
        event_type: str | None = None,
        limit: int = 100,
    ) -> list[HistoryEntry]:
        async with self._lock:
            entries = list(self._entries)
        if mission_id is not None:
            entries = [e for e in entries if e.mission_id == mission_id]
        if event_type is not None:
            entries = [e for e in entries if e.event_type == event_type]
        entries.sort(key=lambda e: e.timestamp, reverse=True)
        return entries[:limit]

    async def count(self, mission_id: str | None = None) -> int:
        async with self._lock:
            if mission_id is None:
                return len(self._entries)
            return sum(1 for e in self._entries if e.mission_id == mission_id)


class MissionPersistence:
    """Persists mission state to disk as JSON snapshots.

    Each mission is saved as a single JSON file containing the full
    mission state (WBS, decisions, artifacts, etc.). On each save,
    the previous file is overwritten atomically.
    """

    def __init__(self, storage_dir: Path) -> None:
        self._storage_dir = storage_dir
        self._storage_dir.mkdir(parents=True, exist_ok=True)
        self._lock = asyncio.Lock()

    def _snapshot_path(self, mission_id: str) -> Path:
        return self._storage_dir / f"{mission_id}.json"

    async def save(self, mission: Mission) -> None:
        """Save a mission snapshot to disk."""
        async with self._lock:
            path = self._snapshot_path(mission.mission_id)
            # Write to temp file then rename for atomicity
            tmp_path = path.with_suffix(".tmp")
            tmp_path.write_text(
                json.dumps(mission.to_dict(), indent=2, default=str),
                encoding="utf-8",
            )
            tmp_path.replace(path)
            _log.debug("Saved mission snapshot: %s", path)

    async def load(self, mission_id: str) -> Mission | None:
        """Load a mission snapshot from disk."""
        async with self._lock:
            path = self._snapshot_path(mission_id)
            if not path.exists():
                return None
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                return Mission.from_dict(data)
            except (json.JSONDecodeError, KeyError, ValueError) as e:
                _log.warning("Failed to load mission snapshot %s: %s", path, e)
                return None

    async def delete(self, mission_id: str) -> bool:
        """Delete a mission snapshot."""
        async with self._lock:
            path = self._snapshot_path(mission_id)
            if path.exists():
                path.unlink()
                return True
            return False

    async def list_saved_missions(self) -> list[str]:
        """List all saved mission IDs."""
        async with self._lock:
            return [
                p.stem for p in self._storage_dir.glob("*.json") if p.is_file()
            ]


class MissionRecovery:
    """Recovers mission state after a crash or restart.

    Loads all saved mission snapshots and returns them in a state ready
    to resume execution. Missions in EXECUTING state are transitioned
    to PAUSED (since their tasks were interrupted).
    """

    def __init__(self, persistence: MissionPersistence) -> None:
        self._persistence = persistence
        self._state_machine = MissionStateMachine()

    async def recover_all(self) -> list[Mission]:
        """Recover all saved missions.

        Missions in EXECUTING state are transitioned to PAUSED.
        Missions in terminal states (COMPLETED, FAILED, CANCELLED) are
        loaded as-is.
        """
        saved_ids = await self._persistence.list_saved_missions()
        recovered: list[Mission] = []
        for mission_id in saved_ids:
            mission = await self._persistence.load(mission_id)
            if mission is None:
                continue
            # If the mission was executing when we crashed, pause it
            if mission.status == MissionStatus.EXECUTING.value:
                try:
                    self._state_machine.transition(
                        mission, MissionStatus.PAUSED.value,
                        reason="Recovery: system restarted, pausing executing mission",
                        actor="recovery",
                    )
                    await self._persistence.save(mission)
                except Exception as e:
                    _log.warning(
                        "Failed to pause mission %s during recovery: %s",
                        mission_id, e,
                    )
            recovered.append(mission)
            _log.info(
                "Recovered mission '%s' (id=%s, status=%s)",
                mission.title, mission.mission_id, mission.status,
            )
        return recovered


@dataclass
class ReplayResult:
    """Result of replaying a mission."""

    mission_id: str
    events_replayed: int = 0
    final_status: str = ""
    timeline: list[dict[str, Any]] = field(default_factory=list)
    duration_s: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "mission_id": self.mission_id,
            "events_replayed": self.events_replayed,
            "final_status": self.final_status,
            "timeline": list(self.timeline),
            "duration_s": round(self.duration_s, 4),
        }


class MissionReplay:
    """Replays mission history to reconstruct state + timeline.

    Given a mission + its history entries, reconstructs the timeline
    of what happened during execution. Useful for debugging, auditing,
    and comparing missions.
    """

    def __init__(self, history: MissionHistory) -> None:
        self._history = history

    async def replay(
        self,
        mission: Mission,
        *,
        speed: float = 1.0,  # replay speed multiplier (0 = instant)
    ) -> ReplayResult:
        """Replay a mission's history.

        Args:
            mission: The mission to replay
            speed: Replay speed (1.0 = real-time, 0 = instant)
        """
        import time
        start = time.perf_counter()
        entries = await self._history.get_history(mission.mission_id, limit=10000)
        entries.reverse()  # chronological order (oldest first)

        timeline: list[dict[str, Any]] = []
        for entry in entries:
            timeline.append({
                "timestamp": entry.timestamp.isoformat(),
                "event_type": entry.event_type,
                "description": entry.description,
                "data": entry.data,
            })
            if speed > 0:
                # In real replay, we'd sleep here to simulate timing
                await asyncio.sleep(0)

        elapsed = time.perf_counter() - start
        return ReplayResult(
            mission_id=mission.mission_id,
            events_replayed=len(entries),
            final_status=mission.status,
            timeline=timeline,
            duration_s=elapsed,
        )

    async def compare_missions(
        self,
        mission1: Mission,
        mission2: Mission,
    ) -> dict[str, Any]:
        """Compare two missions' histories."""
        entries1 = await self._history.get_history(mission1.mission_id, limit=1000)
        entries2 = await self._history.get_history(mission2.mission_id, limit=1000)
        return {
            "mission1": {
                "id": mission1.mission_id,
                "title": mission1.title,
                "status": mission1.status,
                "history_entries": len(entries1),
                "wbs_nodes": len(mission1.wbs_nodes),
                "decisions": len(mission1.decisions),
                "duration_s": mission1.elapsed_s(),
            },
            "mission2": {
                "id": mission2.mission_id,
                "title": mission2.title,
                "status": mission2.status,
                "history_entries": len(entries2),
                "wbs_nodes": len(mission2.wbs_nodes),
                "decisions": len(mission2.decisions),
                "duration_s": mission2.elapsed_s(),
            },
            "differences": {
                "wbs_node_delta": len(mission1.wbs_nodes) - len(mission2.wbs_nodes),
                "decision_delta": len(mission1.decisions) - len(mission2.decisions),
                "duration_delta_s": mission1.elapsed_s() - mission2.elapsed_s(),
                "cost_delta_usd": mission1.budget.spent_usd - mission2.budget.spent_usd,
            },
        }
