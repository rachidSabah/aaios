"""Resource Manager — dynamic allocation of agents, providers, memory, budget.

Manages the pool of resources available to missions:
  - Agent assignment + load balancing
  - Provider selection + failover
  - Memory / CPU / GPU / storage limits
  - Budget tracking + reservation
  - Concurrency limits (max concurrent tasks/agents per mission)
  - Priority-based allocation
"""

from __future__ import annotations

import asyncio
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from core.logging import get_logger
from services.organization.models import Mission

_log = get_logger(__name__)

__all__ = [
    "AgentAssignment",
    "ProviderAssignment",
    "ResourceManager",
    "ResourcePool",
    "ResourceUtilization",
]


@dataclass
class AgentAssignment:
    """An agent assigned to a mission/task."""

    agent_id: str
    mission_id: str
    wbs_node_id: str | None = None
    assigned_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    released_at: datetime | None = None
    task_count: int = 0

    @property
    def is_active(self) -> bool:
        return self.released_at is None


@dataclass
class ProviderAssignment:
    """A provider assigned to a mission/task."""

    provider: str
    mission_id: str
    wbs_node_id: str | None = None
    assigned_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    released_at: datetime | None = None
    request_count: int = 0

    @property
    def is_active(self) -> bool:
        return self.released_at is None


@dataclass
class ResourceUtilization:
    """Current resource utilization across all missions."""

    total_agents_assigned: int = 0
    total_providers_assigned: int = 0
    active_missions: int = 0
    total_concurrent_tasks: int = 0
    total_budget_reserved_usd: float = 0.0
    total_budget_spent_usd: float = 0.0
    by_mission: dict[str, dict[str, Any]] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_agents_assigned": self.total_agents_assigned,
            "total_providers_assigned": self.total_providers_assigned,
            "active_missions": self.active_missions,
            "total_concurrent_tasks": self.total_concurrent_tasks,
            "total_budget_reserved_usd": round(self.total_budget_reserved_usd, 6),
            "total_budget_spent_usd": round(self.total_budget_spent_usd, 6),
            "by_mission": dict(self.by_mission),
        }


@dataclass
class ResourcePool:
    """The global pool of available resources."""

    available_agents: list[str] = field(default_factory=list)
    available_providers: list[str] = field(default_factory=list)
    max_total_concurrent_tasks: int = 500
    max_total_concurrent_agents: int = 500
    max_mission_concurrent_tasks: int = 50
    global_memory_limit_mb: int = 32768
    global_cpu_cores: float = 16.0
    global_gpu_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "available_agents": list(self.available_agents),
            "available_providers": list(self.available_providers),
            "max_total_concurrent_tasks": self.max_total_concurrent_tasks,
            "max_total_concurrent_agents": self.max_total_concurrent_agents,
            "max_mission_concurrent_tasks": self.max_mission_concurrent_tasks,
            "global_memory_limit_mb": self.global_memory_limit_mb,
            "global_cpu_cores": self.global_cpu_cores,
            "global_gpu_count": self.global_gpu_count,
        }


class ResourceManager:
    """Manages dynamic resource allocation across missions.

    Tracks agent/provider assignments, enforces concurrency limits,
    and provides load balancing across available resources.
    """

    def __init__(
        self,
        pool: ResourcePool | None = None,
    ) -> None:
        self._pool = pool or ResourcePool()
        self._agent_assignments: dict[str, list[AgentAssignment]] = defaultdict(list)
        self._provider_assignments: dict[str, list[ProviderAssignment]] = defaultdict(list)
        self._mission_concurrent_tasks: dict[str, int] = defaultdict(int)
        self._total_concurrent_tasks: int = 0
        self._lock = asyncio.Lock()

    @property
    def pool(self) -> ResourcePool:
        return self._pool

    async def assign_agent(
        self,
        mission_id: str,
        agent_id: str,
        *,
        wbs_node_id: str | None = None,
    ) -> AgentAssignment:
        """Assign an agent to a mission/task."""
        async with self._lock:
            assignment = AgentAssignment(
                agent_id=agent_id,
                mission_id=mission_id,
                wbs_node_id=wbs_node_id,
            )
            self._agent_assignments[agent_id].append(assignment)
            _log.info(
                "Assigned agent '%s' to mission '%s' (task=%s)",
                agent_id, mission_id, wbs_node_id,
            )
            return assignment

    async def release_agent(
        self,
        mission_id: str,
        agent_id: str,
        *,
        wbs_node_id: str | None = None,
    ) -> bool:
        """Release an agent from a mission/task."""
        async with self._lock:
            for assignment in self._agent_assignments.get(agent_id, []):
                if (
                    assignment.mission_id == mission_id
                    and assignment.is_active
                    and (wbs_node_id is None or assignment.wbs_node_id == wbs_node_id)
                ):
                    assignment.released_at = datetime.now(UTC)
                    return True
            return False

    async def assign_provider(
        self,
        mission_id: str,
        provider: str,
        *,
        wbs_node_id: str | None = None,
    ) -> ProviderAssignment:
        """Assign a provider to a mission/task."""
        async with self._lock:
            assignment = ProviderAssignment(
                provider=provider,
                mission_id=mission_id,
                wbs_node_id=wbs_node_id,
            )
            self._provider_assignments[provider].append(assignment)
            _log.info(
                "Assigned provider '%s' to mission '%s' (task=%s)",
                provider, mission_id, wbs_node_id,
            )
            return assignment

    async def release_provider(
        self,
        mission_id: str,
        provider: str,
        *,
        wbs_node_id: str | None = None,
    ) -> bool:
        """Release a provider from a mission/task."""
        async with self._lock:
            for assignment in self._provider_assignments.get(provider, []):
                if (
                    assignment.mission_id == mission_id
                    and assignment.is_active
                    and (wbs_node_id is None or assignment.wbs_node_id == wbs_node_id)
                ):
                    assignment.released_at = datetime.now(UTC)
                    return True
            return False

    async def acquire_task_slot(self, mission_id: str) -> bool:
        """Acquire a concurrent task slot for a mission.

        Returns True if a slot was acquired, False if limits exceeded.
        """
        async with self._lock:
            if self._total_concurrent_tasks >= self._pool.max_total_concurrent_tasks:
                return False
            if self._mission_concurrent_tasks[mission_id] >= self._pool.max_mission_concurrent_tasks:
                return False
            self._total_concurrent_tasks += 1
            self._mission_concurrent_tasks[mission_id] += 1
            return True

    async def release_task_slot(self, mission_id: str) -> None:
        """Release a concurrent task slot."""
        async with self._lock:
            if self._total_concurrent_tasks > 0:
                self._total_concurrent_tasks -= 1
            if self._mission_concurrent_tasks[mission_id] > 0:
                self._mission_concurrent_tasks[mission_id] -= 1

    async def reserve_budget(
        self,
        mission: Mission,
        amount_usd: float,
    ) -> bool:
        """Reserve budget for an upcoming task. Returns True if reservation fits."""
        if mission.budget.remaining_usd < amount_usd:
            return False
        mission.budget.reserved_usd += amount_usd
        return True

    async def release_budget_reservation(
        self,
        mission: Mission,
        amount_usd: float,
    ) -> None:
        """Release a budget reservation."""
        mission.budget.reserved_usd = max(0, mission.budget.reserved_usd - amount_usd)

    async def spend_budget(
        self,
        mission: Mission,
        amount_usd: float,
    ) -> bool:
        """Spend budget (moves from reserved to spent). Returns True if successful."""
        if mission.budget.remaining_usd + mission.budget.reserved_usd < amount_usd:
            return False
        # First release from reserved, then spend
        mission.budget.reserved_usd = max(0, mission.budget.reserved_usd - amount_usd)
        mission.budget.spent_usd += amount_usd
        return True

    async def select_least_loaded_agent(
        self,
        available_agents: list[str] | None = None,
    ) -> str | None:
        """Select the agent with the fewest active assignments."""
        candidates = available_agents or self._pool.available_agents
        if not candidates:
            return None
        async with self._lock:
            # Count active assignments per agent
            load: dict[str, int] = {}
            for agent_id in candidates:
                load[agent_id] = sum(
                    1 for a in self._agent_assignments.get(agent_id, []) if a.is_active
                )
            # Return the least-loaded
            return min(candidates, key=lambda a: load.get(a, 0))

    async def select_least_loaded_provider(
        self,
        available_providers: list[str] | None = None,
    ) -> str | None:
        """Select the provider with the fewest active assignments."""
        candidates = available_providers or self._pool.available_providers
        if not candidates:
            return None
        async with self._lock:
            load: dict[str, int] = {}
            for provider in candidates:
                load[provider] = sum(
                    1 for a in self._provider_assignments.get(provider, []) if a.is_active
                )
            return min(candidates, key=lambda p: load.get(p, 0))

    async def get_utilization(self) -> ResourceUtilization:
        """Get current resource utilization."""
        async with self._lock:
            total_agents = sum(
                1 for assignments in self._agent_assignments.values()
                for a in assignments if a.is_active
            )
            total_providers = sum(
                1 for assignments in self._provider_assignments.values()
                for a in assignments if a.is_active
            )
            active_mission_ids = {
                a.mission_id for assignments in self._agent_assignments.values()
                for a in assignments if a.is_active
            }
            by_mission: dict[str, dict[str, Any]] = {}
            for mid in active_mission_ids:
                agents = sum(
                    1 for assignments in self._agent_assignments.values()
                    for a in assignments if a.is_active and a.mission_id == mid
                )
                providers = sum(
                    1 for assignments in self._provider_assignments.values()
                    for a in assignments if a.is_active and a.mission_id == mid
                )
                by_mission[mid] = {
                    "agents": agents,
                    "providers": providers,
                    "concurrent_tasks": self._mission_concurrent_tasks.get(mid, 0),
                }
            return ResourceUtilization(
                total_agents_assigned=total_agents,
                total_providers_assigned=total_providers,
                active_missions=len(active_mission_ids),
                total_concurrent_tasks=self._total_concurrent_tasks,
                by_mission=by_mission,
            )

    async def get_agent_load(self, agent_id: str) -> int:
        """Get the number of active assignments for an agent."""
        async with self._lock:
            return sum(
                1 for a in self._agent_assignments.get(agent_id, []) if a.is_active
            )

    async def get_provider_load(self, provider: str) -> int:
        """Get the number of active assignments for a provider."""
        async with self._lock:
            return sum(
                1 for a in self._provider_assignments.get(provider, []) if a.is_active
            )

    async def release_all_for_mission(self, mission_id: str) -> int:
        """Release all resources for a mission. Returns count released."""
        count = 0
        async with self._lock:
            for agent_id, agent_assignments in self._agent_assignments.items():
                for aa in agent_assignments:
                    if aa.mission_id == mission_id and aa.is_active:
                        aa.released_at = datetime.now(UTC)
                        count += 1
            for provider, provider_assignments in self._provider_assignments.items():
                for pa in provider_assignments:
                    if pa.mission_id == mission_id and pa.is_active:
                        pa.released_at = datetime.now(UTC)
                        count += 1
            # Release task slots
            slots = self._mission_concurrent_tasks.pop(mission_id, 0)
            self._total_concurrent_tasks = max(0, self._total_concurrent_tasks - slots)
        return count
