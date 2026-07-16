"""MissionManager — the top-level facade for the Autonomous Mission System.

Wires together all subsystems:
  - MissionStore (persistence)
  - MissionStateMachine (lifecycle)
  - WorkBreakdownEngine (decomposition)
  - DecisionEngine (executive decisions)
  - CollaborationEngine (multi-agent collaboration)
  - ResourceManager (agent/provider/budget allocation)
  - MissionPersistence + MissionRecovery + MissionReplay (lifecycle)
  - MissionAnalytics + MissionSearcher + MissionExporter (reporting)

Usage:
    manager = MissionManager(storage_dir=Path("/var/lib/aaios/missions"))
    await manager.start()  # recovers missions from disk
    mission = await manager.create_mission(
        title="Build web app",
        objectives=["Set up backend", "Build frontend", "Deploy"],
        budget_total_usd=100.0,
    )
    await manager.start_mission(mission.mission_id)
    # ... execution happens via WBS + DecisionEngine ...
    await manager.pause_mission(mission.mission_id)
    await manager.resume_mission(mission.mission_id)
    await manager.complete_mission(mission.mission_id)
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from core.contracts.actor import ActorRef, ActorType
from core.contracts.event import Event
from core.event_bus import EventBus
from core.logging import get_logger
from services.organization.analytics import (
    MissionAnalytics,
    MissionExporter,
    MissionSearcher,
    PortfolioMetrics,
)
from services.organization.collaboration import CollaborationEngine
from services.organization.decision_engine import (
    DecisionEngine,
    DecisionRecommendation,
)
from services.organization.models import (
    Budget,
    Decision,
    Mission,
    MissionPriority,
    MissionStatus,
    WBSNode,
    WBSType,
)
from services.organization.persistence import (
    HistoryEntry,
    MissionHistory,
    MissionPersistence,
    MissionRecovery,
    MissionReplay,
    ReplayResult,
)
from services.organization.resource_manager import (
    ResourceManager,
    ResourcePool,
    ResourceUtilization,
)
from services.organization.state_machine import (
    IllegalTransitionError,
    MissionStateMachine,
    MissionStateTransition,
)
from services.organization.store import (
    MissionFilter,
    MissionNotFoundError,
    MissionStore,
    MissionSummary,
)
from services.organization.wbs_engine import WorkBreakdownEngine

_log = get_logger(__name__)

__all__ = [
    "IllegalTransitionError",
    "MissionFilter",
    "MissionManager",
    "MissionNotFoundError",
    "MissionPriority",
    "MissionStatus",
    "MissionSummary",
    "PortfolioMetrics",
    "ReplayResult",
    "WBSType",
]


class MissionManager:
    """Top-level facade for the Autonomous Mission & Organization System.

    Call `start()` once at boot to recover missions from disk and
    subscribe to the event bus. After that, missions can be created,
    started, paused, resumed, cancelled, and completed.
    """

    def __init__(
        self,
        *,
        storage_dir: Path | None = None,
        resource_pool: ResourcePool | None = None,
    ) -> None:
        self.store = MissionStore(storage_dir=storage_dir)
        self.state_machine = MissionStateMachine()
        self.wbs_engine = WorkBreakdownEngine()
        self.decision_engine = DecisionEngine(self.state_machine)
        self.collaboration = CollaborationEngine()
        self.resources = ResourceManager(pool=resource_pool)
        self.history = MissionHistory()
        self.persistence = (
            MissionPersistence(storage_dir / "snapshots")
            if storage_dir
            else MissionPersistence(Path("/tmp/aaios/missions/snapshots"))
        )
        self.recovery = MissionRecovery(self.persistence)
        self.replay = MissionReplay(self.history)
        self.analytics = MissionAnalytics(self.store)
        self.searcher = MissionSearcher(self.store)
        self.exporter = MissionExporter(self.store)
        self._bus: EventBus | None = None
        self._started = False

    async def start(self, bus: EventBus | None = None) -> None:
        """Start the mission manager. Recovers missions from disk."""
        if self._started:
            return
        self._bus = bus
        # Recover missions from disk
        recovered = await self.recovery.recover_all()
        for mission in recovered:
            try:
                await self.store.create(mission)
            except ValueError:
                # Already in store (from store's own _load_all)
                pass
        _log.info("MissionManager started — recovered %d missions", len(recovered))
        self._started = True

    async def stop(self) -> None:
        """Stop the mission manager."""
        self._started = False
        _log.info("MissionManager stopped")

    # --- Event publishing ---

    async def _publish_event(
        self,
        topic: str,
        payload: dict[str, Any],
        *,
        mission_id: str | None = None,
    ) -> None:
        """Publish an event on the mission event bus."""
        if self._bus is None:
            return
        try:
            event = Event(
                topic=topic,
                correlation_id=uuid4(),
                actor=ActorRef(type=ActorType.SYSTEM, id="mission_manager"),
                payload={**payload, "mission_id": mission_id} if mission_id else payload,
            )
            await self._bus.publish(event)
        except Exception as e:
            _log.warning("Failed to publish event %s: %s", topic, e)

    async def _record_history(
        self,
        mission_id: str,
        event_type: str,
        description: str,
        data: dict[str, Any] | None = None,
    ) -> None:
        """Record a history entry."""
        entry = HistoryEntry(
            mission_id=mission_id,
            event_type=event_type,
            description=description,
            data=data or {},
        )
        await self.history.add(entry)

    # --- Mission CRUD ---

    async def create_mission(
        self,
        *,
        title: str,
        description: str = "",
        objectives: list[str] | None = None,
        deliverables: list[str] | None = None,
        priority: str = MissionPriority.NORMAL.value,
        budget_total_usd: float = 0.0,
        deadline: datetime | None = None,
        owner: str | None = None,
        tags: list[str] | None = None,
        mission_director: str | None = None,
        depends_on: list[str] | None = None,
        decompose: bool = True,
        decomposition_strategy: str = "objective_per_project",
    ) -> Mission:
        """Create a new mission."""
        mission = Mission(
            title=title,
            description=description,
            objectives=objectives or [],
            deliverables=deliverables or [],
            priority=priority,
            budget=Budget(total_usd=budget_total_usd),
            deadline=deadline,
            owner=owner,
            tags=tags or [],
            mission_director=mission_director,
            depends_on_missions=depends_on or [],
        )
        # Optionally decompose into WBS
        if decompose and mission.objectives:
            self.wbs_engine.decompose(mission, strategy=decomposition_strategy)

        await self.store.create(mission)
        await self.persistence.save(mission)
        await self._record_history(
            mission.mission_id, "mission_created",
            f"Mission '{title}' created with {len(mission.wbs_nodes)} WBS nodes",
        )
        await self._publish_event(
            "mission.created",
            {"title": title, "priority": priority, "wbs_node_count": len(mission.wbs_nodes)},
            mission_id=mission.mission_id,
        )
        return mission

    async def get_mission(self, mission_id: str) -> Mission:
        """Get a mission by ID."""
        return await self.store.get(mission_id)

    async def list_missions(
        self,
        filter: MissionFilter | None = None,
        *,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Mission]:
        """List missions with optional filtering."""
        return await self.store.query(filter, limit=limit, offset=offset)

    async def update_mission(
        self,
        mission_id: str,
        changes: dict[str, Any],
    ) -> Mission:
        """Update a mission's fields."""
        mission = await self.store.get(mission_id)
        if "title" in changes:
            mission.title = changes["title"]
        if "description" in changes:
            mission.description = changes["description"]
        if "priority" in changes:
            mission.priority = changes["priority"]
        if "deadline" in changes:
            mission.deadline = changes["deadline"]
        if "owner" in changes:
            mission.owner = changes["owner"]
        if "tags" in changes:
            mission.tags = list(changes["tags"])
        if "budget_total_usd" in changes:
            mission.budget.total_usd = changes["budget_total_usd"]
        updated = await self.store.update(mission)
        await self.persistence.save(updated)
        await self._record_history(mission_id, "mission_updated", f"Mission updated: {list(changes.keys())}")
        return updated

    async def delete_mission(self, mission_id: str) -> bool:
        """Delete a mission."""
        deleted = await self.store.delete(mission_id)
        if deleted:
            await self.persistence.delete(mission_id)
            await self._publish_event("mission.deleted", {}, mission_id=mission_id)
        return deleted

    # --- Lifecycle ---

    async def start_mission(self, mission_id: str) -> Mission:
        """Start a mission: transition to PLANNING → READY → EXECUTING."""
        mission = await self.store.get(mission_id)
        # If in CREATED, move to PLANNING
        if mission.status == MissionStatus.CREATED.value:
            transition = self.state_machine.transition(
                mission, MissionStatus.PLANNING.value,
                reason="Starting mission", actor="mission_manager",
            )
            await self._publish_transition(mission, transition)
        # If in PLANNING, move to READY
        if mission.status == MissionStatus.PLANNING.value:
            transition = self.state_machine.transition(
                mission, MissionStatus.READY.value,
                reason="Planning complete", actor="mission_manager",
            )
            await self._publish_transition(mission, transition)
        # If in READY, move to EXECUTING
        if mission.status == MissionStatus.READY.value:
            transition = self.state_machine.transition(
                mission, MissionStatus.EXECUTING.value,
                reason="Starting execution", actor="mission_manager",
            )
            await self._publish_transition(mission, transition)
        updated = await self.store.update(mission)
        await self.persistence.save(updated)
        await self._record_history(mission_id, "mission_started", "Mission execution started")
        return updated

    async def pause_mission(self, mission_id: str, *, reason: str = "") -> Mission:
        """Pause a mission."""
        mission = await self.store.get(mission_id)
        transition = self.state_machine.transition(
            mission, MissionStatus.PAUSED.value,
            reason=reason or "User requested pause", actor="mission_manager",
        )
        await self._publish_transition(mission, transition)
        updated = await self.store.update(mission)
        await self.persistence.save(updated)
        await self._record_history(mission_id, "mission_paused", f"Mission paused: {reason}")
        return updated

    async def resume_mission(self, mission_id: str) -> Mission:
        """Resume a paused mission."""
        mission = await self.store.get(mission_id)
        transition = self.state_machine.transition(
            mission, MissionStatus.EXECUTING.value,
            reason="User requested resume", actor="mission_manager",
        )
        await self._publish_transition(mission, transition)
        updated = await self.store.update(mission)
        await self.persistence.save(updated)
        await self._record_history(mission_id, "mission_resumed", "Mission resumed")
        return updated

    async def cancel_mission(self, mission_id: str, *, reason: str = "") -> Mission:
        """Cancel a mission."""
        mission = await self.store.get(mission_id)
        transition = self.state_machine.transition(
            mission, MissionStatus.CANCELLED.value,
            reason=reason or "User requested cancellation", actor="mission_manager",
        )
        await self._publish_transition(mission, transition)
        # Release all resources
        await self.resources.release_all_for_mission(mission_id)
        updated = await self.store.update(mission)
        await self.persistence.save(updated)
        await self._record_history(mission_id, "mission_cancelled", f"Mission cancelled: {reason}")
        return updated

    async def complete_mission(self, mission_id: str) -> Mission:
        """Mark a mission as completed."""
        mission = await self.store.get(mission_id)
        transition = self.state_machine.transition(
            mission, MissionStatus.COMPLETED.value,
            reason="All objectives achieved", actor="mission_manager",
        )
        await self._publish_transition(mission, transition)
        await self.resources.release_all_for_mission(mission_id)
        updated = await self.store.update(mission)
        await self.persistence.save(updated)
        await self._record_history(mission_id, "mission_completed", "Mission completed successfully")
        return updated

    async def fail_mission(self, mission_id: str, *, reason: str = "") -> Mission:
        """Mark a mission as failed."""
        mission = await self.store.get(mission_id)
        transition = self.state_machine.transition(
            mission, MissionStatus.FAILED.value,
            reason=reason or "Mission failed", actor="mission_manager",
        )
        await self._publish_transition(mission, transition)
        await self.resources.release_all_for_mission(mission_id)
        updated = await self.store.update(mission)
        await self.persistence.save(updated)
        await self._record_history(mission_id, "mission_failed", f"Mission failed: {reason}")
        return updated

    async def replan_mission(self, mission_id: str, *, reason: str = "") -> Mission:
        """Replan a mission — transition back to PLANNING."""
        mission = await self.store.get(mission_id)
        transition = self.state_machine.transition(
            mission, MissionStatus.PLANNING.value,
            reason=reason or "Replanning requested", actor="mission_manager",
        )
        await self._publish_transition(mission, transition)
        updated = await self.store.update(mission)
        await self.persistence.save(updated)
        await self._record_history(mission_id, "mission_replanned", f"Mission replanned: {reason}")
        return updated

    async def _publish_transition(
        self,
        mission: Mission,
        transition: MissionStateTransition,
    ) -> None:
        """Publish a state transition event."""
        await self._publish_event(
            transition.event_topic,
            {
                "from_state": transition.from_state,
                "to_state": transition.to_state,
                "reason": transition.reason,
                "actor": transition.actor,
            },
            mission_id=mission.mission_id,
        )

    # --- WBS operations ---

    async def add_wbs_node(
        self,
        mission_id: str,
        node_type: str,
        *,
        title: str,
        description: str = "",
        parent_id: str | None = None,
        depends_on: list[str] | None = None,
        capabilities_required: list[str] | None = None,
        assigned_agent_id: str | None = None,
        assigned_provider: str | None = None,
    ) -> WBSNode:
        """Add a WBS node to a mission."""
        mission = await self.store.get(mission_id)
        node = self.wbs_engine.add_node(
            mission,
            node_type,
            title=title,
            description=description,
            parent_id=parent_id,
            depends_on=depends_on,
            capabilities_required=capabilities_required,
            assigned_agent_id=assigned_agent_id,
            assigned_provider=assigned_provider,
        )
        await self.store.update(mission)
        await self.persistence.save(mission)
        await self._record_history(
            mission_id, "wbs_node_added",
            f"WBS node '{title}' added (type={node_type})",
            {"node_id": node.node_id},
        )
        return node

    async def complete_wbs_node(
        self,
        mission_id: str,
        node_id: str,
        *,
        status: str = "succeeded",
    ) -> Mission:
        """Mark a WBS node as complete."""
        mission = await self.store.get(mission_id)
        node = mission.get_wbs_node(node_id)
        if node is None:
            raise ValueError(f"WBS node {node_id} not found in mission {mission_id}")
        node.status = status
        node.completed_at = datetime.now(UTC)
        if node.started_at:
            node.actual_duration_s = (node.completed_at - node.started_at).total_seconds()
        await self.store.update(mission)
        await self.persistence.save(mission)
        await self._record_history(
            mission_id, "wbs_node_completed",
            f"WBS node '{node.title}' {status}",
            {"node_id": node_id, "status": status},
        )
        return mission

    async def get_ready_nodes(self, mission_id: str) -> list[WBSNode]:
        """Get WBS nodes that are ready to execute."""
        mission = await self.store.get(mission_id)
        return mission.get_ready_nodes()

    async def get_execution_layers(self, mission_id: str) -> list[list[str]]:
        """Get execution layers (parallelizable groups) for a mission."""
        mission = await self.store.get(mission_id)
        return self.wbs_engine.get_execution_layers(mission)

    # --- Decision operations ---

    async def evaluate_mission(self, mission_id: str) -> list[DecisionRecommendation]:
        """Evaluate a mission and return decision recommendations."""
        mission = await self.store.get(mission_id)
        return self.decision_engine.evaluate(mission)

    async def make_decision(
        self,
        mission_id: str,
        recommendation: DecisionRecommendation,
    ) -> Decision:
        """Record an executive decision for a mission."""
        mission = await self.store.get(mission_id)
        decision = self.decision_engine.make_decision(mission, recommendation)
        await self.store.update(mission)
        await self.persistence.save(mission)
        await self._publish_event(
            "mission.decision_made",
            {
                "decision_type": decision.decision_type,
                "made_by": decision.made_by,
                "reasoning": decision.reasoning,
            },
            mission_id=mission_id,
        )
        await self._record_history(
            mission_id, "decision",
            f"Decision: {decision.decision_type} by {decision.made_by}",
            decision.to_dict(),
        )
        return decision

    async def recommend_agent_for_task(
        self,
        mission_id: str,
        node_id: str,
        *,
        available_agents: list[str] | None = None,
    ) -> DecisionRecommendation:
        """Recommend an agent for a WBS node."""
        mission = await self.store.get(mission_id)
        node = mission.get_wbs_node(node_id)
        if node is None:
            raise ValueError(f"Node {node_id} not found")
        return self.decision_engine.select_agent_for_task(
            mission, node, available_agents=available_agents,
        )

    # --- Analytics + Search + Export ---

    async def get_portfolio_metrics(self) -> PortfolioMetrics:
        """Get portfolio-level metrics."""
        return await self.analytics.portfolio_metrics()

    async def get_mission_timeline(self, mission_id: str) -> list[dict[str, Any]]:
        """Get a mission's event timeline."""
        mission = await self.store.get(mission_id)
        timeline = await self.analytics.mission_timeline(mission)
        return [t.to_dict() for t in timeline]

    async def get_mission_graph(self, mission_id: str) -> dict[str, Any]:
        """Get a mission's WBS dependency graph."""
        mission = await self.store.get(mission_id)
        return await self.analytics.mission_graph(mission)

    async def get_mission_analytics(self, mission_id: str) -> dict[str, Any]:
        """Get analytics for a single mission."""
        mission = await self.store.get(mission_id)
        return {
            "mission_id": mission_id,
            "status": mission.status,
            "metrics": mission.metrics.to_dict(),
            "quality": mission.quality.to_dict(),
            "budget": mission.budget.to_dict(),
            "wbs_summary": {
                "total": len(mission.wbs_nodes),
                "by_status": dict(Counter(n.status for n in mission.wbs_nodes)),
                "by_type": dict(Counter(n.node_type for n in mission.wbs_nodes)),
            },
            "decisions": len(mission.decisions),
            "artifacts": len(mission.artifacts),
            "risks": len(mission.risks),
            "milestones": len(mission.milestones),
            "elapsed_s": mission.elapsed_s(),
        }

    async def search_missions(
        self,
        query: str,
        *,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Search missions by text."""
        results = await self.searcher.search(query, limit=limit)
        return [r.to_dict() for r in results]

    async def replay_mission(self, mission_id: str) -> ReplayResult:
        """Replay a mission's history."""
        mission = await self.store.get(mission_id)
        result = await self.replay.replay(mission)
        return result

    async def export_missions_json(
        self,
        filter: MissionFilter | None = None,
        *,
        limit: int = 1000,
    ) -> str:
        """Export missions as JSON."""
        return await self.exporter.export_json(filter, limit=limit)

    async def export_missions_csv(
        self,
        filter: MissionFilter | None = None,
        *,
        limit: int = 1000,
    ) -> str:
        """Export missions as CSV."""
        return await self.exporter.export_csv(filter, limit=limit)

    async def get_resource_utilization(self) -> ResourceUtilization:
        """Get current resource utilization."""
        return await self.resources.get_utilization()

    async def get_mission_summary(self) -> MissionSummary:
        """Get summary across all missions."""
        return await self.store.summarize()

    async def get_mission_history(
        self,
        mission_id: str,
        *,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Get history entries for a mission."""
        entries = await self.history.get_history(mission_id, limit=limit)
        return [e.to_dict() for e in entries]

    async def recover_missions(self) -> list[Mission]:
        """Recover missions from disk (for testing)."""
        return await self.recovery.recover_all()


from collections import Counter  # noqa: E402
