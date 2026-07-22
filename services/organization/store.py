"""Mission Store — persistent storage for Missions.

Persists each mission as a JSON file. Maintains in-memory indices for
fast lookup by status, priority, owner, and tags.
"""

from __future__ import annotations

import asyncio
import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

from core.logging import get_logger
from services.organization.models import Mission

_log = get_logger(__name__)

__all__ = [
    "MissionFilter",
    "MissionNotFoundError",
    "MissionStore",
    "MissionSummary",
]


class MissionNotFoundError(Exception):
    """Raised when a mission ID is not found."""


from dataclasses import dataclass, field  # noqa: E402


@dataclass
class MissionFilter:
    """Filter for querying missions."""

    status: str | None = None
    priority: str | None = None
    owner: str | None = None
    tag: str | None = None
    mission_director: str | None = None
    since: datetime | None = None
    until: datetime | None = None

    def matches(self, mission: Mission) -> bool:
        if self.status is not None and mission.status != self.status:
            return False
        if self.priority is not None and mission.priority != self.priority:
            return False
        if self.owner is not None and mission.owner != self.owner:
            return False
        if self.tag is not None and self.tag not in mission.tags:
            return False
        if self.mission_director is not None and mission.mission_director != self.mission_director:
            return False
        if self.since is not None and mission.created_at < self.since:
            return False
        if self.until is not None and mission.created_at > self.until:
            return False
        return True


@dataclass
class MissionSummary:
    """Aggregated summary across missions."""

    total_missions: int = 0
    by_status: dict[str, int] = field(default_factory=dict)
    by_priority: dict[str, int] = field(default_factory=dict)
    total_budget_usd: float = 0.0
    total_spent_usd: float = 0.0
    total_wbs_nodes: int = 0
    total_completed_nodes: int = 0
    total_artifacts: int = 0
    total_decisions: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_missions": self.total_missions,
            "by_status": dict(self.by_status),
            "by_priority": dict(self.by_priority),
            "total_budget_usd": round(self.total_budget_usd, 2),
            "total_spent_usd": round(self.total_spent_usd, 2),
            "total_wbs_nodes": self.total_wbs_nodes,
            "total_completed_nodes": self.total_completed_nodes,
            "total_artifacts": self.total_artifacts,
            "total_decisions": self.total_decisions,
        }


class MissionStore:
    """Persistent store for missions.

    Records are stored as individual JSON files. An in-memory index enables
    fast queries by status, priority, owner, and tags.
    """

    def __init__(self, storage_dir: Path | None = None) -> None:
        self._storage_dir = storage_dir
        self._missions: dict[str, Mission] = {}
        self._by_status: dict[str, list[str]] = defaultdict(list)
        self._by_priority: dict[str, list[str]] = defaultdict(list)
        self._by_owner: dict[str, list[str]] = defaultdict(list)
        self._by_tag: dict[str, list[str]] = defaultdict(list)
        self._lock = asyncio.Lock()
        if storage_dir is not None:
            storage_dir.mkdir(parents=True, exist_ok=True)
            self._load_all()

    def _mission_path(self, mission_id: str) -> Path:
        if self._storage_dir is None:
            raise RuntimeError("No storage directory configured")
        return self._storage_dir / f"{mission_id}.json"

    def _load_all(self) -> None:
        if self._storage_dir is None:
            return
        for path in self._storage_dir.glob("*.json"):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                mission = Mission.from_dict(data)
                self._missions[mission.mission_id] = mission
                self._index_mission(mission)
            except (json.JSONDecodeError, KeyError, ValueError) as e:
                _log.warning("Failed to load mission from %s: %s", path, e)

    def _index_mission(self, mission: Mission) -> None:
        self._by_status[mission.status].append(mission.mission_id)
        self._by_priority[mission.priority].append(mission.mission_id)
        if mission.owner:
            self._by_owner[mission.owner].append(mission.mission_id)
        for tag in mission.tags:
            self._by_tag[tag].append(mission.mission_id)

    def _persist(self, mission: Mission) -> None:
        if self._storage_dir is None:
            return
        path = self._mission_path(mission.mission_id)
        path.write_text(
            json.dumps(mission.to_dict(), indent=2, default=str),
            encoding="utf-8",
        )

    def _delete_persisted(self, mission_id: str) -> None:
        if self._storage_dir is None:
            return
        path = self._mission_path(mission_id)
        if path.exists():
            path.unlink()

    async def create(self, mission: Mission) -> Mission:
        """Store a new mission."""
        async with self._lock:
            if mission.mission_id in self._missions:
                raise ValueError(f"Mission {mission.mission_id} already exists")
            self._missions[mission.mission_id] = mission
            self._index_mission(mission)
            self._persist(mission)
            _log.info("Created mission '%s' (id=%s)", mission.title, mission.mission_id)
            return mission

    async def get(self, mission_id: str) -> Mission:
        """Retrieve a mission by ID."""
        async with self._lock:
            if mission_id not in self._missions:
                raise MissionNotFoundError(f"Mission {mission_id} not found")
            return self._missions[mission_id]

    async def update(self, mission: Mission) -> Mission:
        """Update an existing mission."""
        from datetime import UTC, datetime

        async with self._lock:
            if mission.mission_id not in self._missions:
                raise MissionNotFoundError(f"Mission {mission.mission_id} not found")
            # Re-index (status/priority may have changed)
            old = self._missions[mission.mission_id]
            if old.status != mission.status:
                self._by_status[old.status].remove(mission.mission_id)
                self._by_status[mission.status].append(mission.mission_id)
            if old.priority != mission.priority:
                self._by_priority[old.priority].remove(mission.mission_id)
                self._by_priority[mission.priority].append(mission.mission_id)
            mission.updated_at = datetime.now(UTC)
            self._missions[mission.mission_id] = mission
            self._persist(mission)
            return mission

    async def delete(self, mission_id: str) -> bool:
        """Delete a mission."""
        async with self._lock:
            if mission_id not in self._missions:
                return False
            mission = self._missions.pop(mission_id)
            self._by_status[mission.status].remove(mission_id)
            if self._by_status[mission.status] and not self._by_status[mission.status]:
                del self._by_status[mission.status]
            self._by_priority[mission.priority].remove(mission_id)
            if self._by_priority[mission.priority] and not self._by_priority[mission.priority]:
                del self._by_priority[mission.priority]
            if mission.owner and mission.owner in self._by_owner:
                self._by_owner[mission.owner].remove(mission_id)
            for tag in mission.tags:
                if tag in self._by_tag:
                    self._by_tag[tag].remove(mission_id)
            self._delete_persisted(mission_id)
            return True

    async def query(
        self,
        filter: MissionFilter | None = None,
        *,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Mission]:
        """Query missions with optional filtering + pagination."""
        async with self._lock:
            missions = list(self._missions.values())
        if filter is not None:
            missions = [m for m in missions if filter.matches(m)]
        missions.sort(key=lambda m: m.created_at, reverse=True)
        return missions[offset : offset + limit]

    async def count(self, filter: MissionFilter | None = None) -> int:
        async with self._lock:
            missions = list(self._missions.values())
        if filter is not None:
            missions = [m for m in missions if filter.matches(m)]
        return len(missions)

    async def list_by_status(self, status: str) -> list[Mission]:
        async with self._lock:
            ids = self._by_status.get(status, [])
            return [self._missions[i] for i in ids if i in self._missions]

    async def summarize(self, filter: MissionFilter | None = None) -> MissionSummary:
        async with self._lock:
            missions = list(self._missions.values())
        if filter is not None:
            missions = [m for m in missions if filter.matches(m)]
        if not missions:
            return MissionSummary()
        by_status: dict[str, int] = defaultdict(int)
        by_priority: dict[str, int] = defaultdict(int)
        for m in missions:
            by_status[m.status] += 1
            by_priority[m.priority] += 1
        return MissionSummary(
            total_missions=len(missions),
            by_status=dict(by_status),
            by_priority=dict(by_priority),
            total_budget_usd=sum(m.budget.total_usd for m in missions),
            total_spent_usd=sum(m.budget.spent_usd for m in missions),
            total_wbs_nodes=sum(len(m.wbs_nodes) for m in missions),
            total_completed_nodes=sum(
                1 for m in missions for n in m.wbs_nodes if n.status == "succeeded"
            ),
            total_artifacts=sum(len(m.artifacts) for m in missions),
            total_decisions=sum(len(m.decisions) for m in missions),
        )

    async def all_missions(self) -> list[Mission]:
        """Return all missions (for export, search, etc.)."""
        async with self._lock:
            return list(self._missions.values())
