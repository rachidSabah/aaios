"""AAiOS API Server — FastAPI REST + WebSocket endpoints.

The single network entry point for all surfaces (CLI, Web UI, Desktop App).
Every operation goes through here. The API server talks to the Supervisor,
Orchestrator, Agent Registry, Memory Manager, Plugin Manager, Security
Layer, and Model Router.

Endpoints:
  /api/v1/tasks      — submit, list, get, pause, resume, cancel
  /api/v1/agents     — list agents, capabilities, health
  /api/v1/memory     — remember, recall, explore
  /api/v1/plugins    — list, install, enable, disable, uninstall
  /api/v1/providers  — list, health, cost
  /api/v1/workflows  — list, run, save
  /api/v1/prompts    — list, render
  /api/v1/audit      — query audit log
  /api/v1/approvals  — list pending, respond
  /ws/events         — live event stream (WebSocket)
  /ws/logs           — live log stream (WebSocket)
  /healthz           — liveness probe
  /readyz            — readiness probe
  /metrics           — Prometheus metrics
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from core.contracts.memory.item import MemoryScope, MemoryScopeType
from core.logging import get_logger
from services.dashboard import (
    Analytics,
    MetricsCollector,
    WorkflowEdge,
    WorkflowNode,
    WorkflowNotFoundError,
    WorkflowStore,
    WorkflowValidationError,
)

_log = get_logger(__name__)

__all__ = ["create_app", "TaskSubmitRequest"]


# ---------------------------------------------------------------------------
# Request/Response models
# ---------------------------------------------------------------------------


class TaskSubmitRequest(BaseModel):
    """Request body for POST /api/v1/tasks."""

    goal: str
    priority: str = Field(default="normal")
    project_id: str | None = None


class TaskSubmitResponse(BaseModel):
    """Response for POST /api/v1/tasks."""

    task_id: str
    status: str


class AgentListResponse(BaseModel):
    """Response for GET /api/v1/agents."""

    agents: list[dict[str, Any]]


class MemoryRememberRequest(BaseModel):
    """Request body for POST /api/v1/memory/remember."""

    scope_type: str = "long_term"
    project_id: str | None = None
    content: str
    content_type: str = "text"
    metadata: dict[str, Any] = Field(default_factory=dict)


class MemoryRecallRequest(BaseModel):
    """Request body for POST /api/v1/memory/recall."""

    scope_type: str | None = None
    project_id: str | None = None
    query: str
    k: int = 10


class MemoryRecallResponse(BaseModel):
    """Response for POST /api/v1/memory/recall."""

    items: list[dict[str, Any]]
    total_found: int
    elapsed_s: float


class PluginActionRequest(BaseModel):
    """Request body for plugin actions."""

    name: str


class ApprovalRespondRequest(BaseModel):
    """Request body for POST /api/v1/approvals/{id}/respond."""

    decision: str  # approved, denied, modified
    modified_inputs: dict[str, Any] | None = None


# --- Dashboard request models (v2.0) ---


class WorkflowCreateRequest(BaseModel):
    """Request body for POST /api/v1/workflows."""

    name: str
    description: str = ""
    nodes: list[dict[str, Any]] = Field(default_factory=list)
    edges: list[dict[str, Any]] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)


class WorkflowUpdateRequest(BaseModel):
    """Request body for PUT /api/v1/workflows/{id}."""

    name: str | None = None
    description: str | None = None
    nodes: list[dict[str, Any]] | None = None
    edges: list[dict[str, Any]] | None = None
    tags: list[str] | None = None


class RecordEventRequest(BaseModel):
    """Request body for POST /api/v1/monitor/record."""

    topic: str
    payload: dict[str, Any] = Field(default_factory=dict)
    correlation_id: str | None = None


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------


def create_app() -> FastAPI:
    """Create the FastAPI application.

    The app is created via a factory so it can be configured with different
    dependencies for testing vs production.
    """
    app = FastAPI(
        title="AAiOS API",
        description="Agentic AI Operating System — REST + WebSocket API",
        version="0.1.0.dev0",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # CORS (for the Next.js dev server)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # tighten in production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # --- Health endpoints ---

    @app.get("/healthz", tags=["health"])
    async def healthz() -> dict[str, Any]:
        """Liveness probe."""
        return {"status": "ok", "version": "0.1.0.dev0", "timestamp": datetime.now(UTC).isoformat()}

    @app.get("/readyz", tags=["health"])
    async def readyz() -> dict[str, Any]:
        """Readiness probe."""
        checks: dict[str, str] = {"process": "alive"}
        # Check if core services are available
        try:
            from services.agent_registry import get_agent_registry

            get_agent_registry()
            checks["agent_registry"] = "ok"
        except RuntimeError:
            checks["agent_registry"] = "not_initialized"
        try:
            from services.model_router import get_model_router

            get_model_router()
            checks["model_router"] = "ok"
        except RuntimeError:
            checks["model_router"] = "not_initialized"
        return {"status": "ok", "checks": checks}

    @app.get("/metrics", tags=["health"])
    async def metrics() -> dict[str, Any]:
        """Basic metrics (Prometheus format would be better, but this works for Phase 12)."""
        return {"status": "ok"}

    # --- Task endpoints ---

    @app.post("/api/v1/tasks", response_model=TaskSubmitResponse, tags=["tasks"])
    async def submit_task(req: TaskSubmitRequest) -> TaskSubmitResponse:
        """Submit a new task (goal)."""
        try:
            # The supervisor is wired at boot; for Phase 12, we use a simplified path
            # that delegates to the supervisor if available, or returns an error
            # In production, this would call the supervisor.submit_goal()
            # For Phase 12, we return a task ID
            task_id = UUID("00000000-0000-0000-0000-000000000000")  # placeholder
            return TaskSubmitResponse(task_id=str(task_id), status="queued")
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e)) from e

    @app.get("/api/v1/tasks", tags=["tasks"])
    async def list_tasks() -> dict[str, Any]:
        """List all tasks."""
        try:
            from orchestrator import get_orchestrator

            orch = get_orchestrator()
            plan_ids = orch.list_active_plans()
            tasks: list[dict[str, Any]] = []
            for pid in plan_ids:
                plan = orch.get_plan(pid)
                status = orch.get_status(pid)
                if plan is not None and status is not None:
                    tasks.append(
                        {
                            "plan_id": str(pid),
                            "task_id": str(plan.task_id),
                            "status": status.value,
                            "step_count": len(plan.steps),
                            "priority": plan.priority,
                        }
                    )
            return {"tasks": tasks, "count": len(tasks)}
        except RuntimeError:
            return {"tasks": [], "count": 0, "error": "orchestrator not initialized"}

    @app.get("/api/v1/tasks/{task_id}", tags=["tasks"])
    async def get_task(task_id: str) -> dict[str, Any]:
        """Get task details."""
        try:
            from orchestrator import get_orchestrator

            orch = get_orchestrator()
            # task_id is actually plan_id for now
            plan = orch.get_plan(UUID(task_id))
            if plan is None:
                raise HTTPException(status_code=404, detail="Task not found")
            status = orch.get_status(UUID(task_id))
            return {
                "plan_id": str(plan.id),
                "task_id": str(plan.task_id),
                "status": status.value if status else "unknown",
                "steps": [
                    {
                        "id": str(s.id),
                        "goal": s.goal,
                        "capability": s.capability,
                        "status": s.status.value,
                        "depends_on": [str(d) for d in s.depends_on],
                    }
                    for s in plan.steps
                ],
            }
        except ValueError as e:
            raise HTTPException(status_code=400, detail=f"Invalid task ID: {e}") from e

    @app.post("/api/v1/tasks/{task_id}/pause", tags=["tasks"])
    async def pause_task(task_id: str) -> dict[str, Any]:
        """Pause a task."""
        try:
            from orchestrator import get_orchestrator

            orch = get_orchestrator()
            result = await orch.pause(UUID(task_id))
            if not result:
                raise HTTPException(status_code=404, detail="Task not found")
            return {"status": "paused"}
        except ValueError as e:
            raise HTTPException(status_code=400, detail=f"Invalid task ID: {e}") from e

    @app.post("/api/v1/tasks/{task_id}/resume", tags=["tasks"])
    async def resume_task(task_id: str) -> dict[str, Any]:
        """Resume a paused task."""
        try:
            from orchestrator import get_orchestrator

            orch = get_orchestrator()
            result = await orch.resume(UUID(task_id))
            if not result:
                raise HTTPException(status_code=404, detail="Task not found or not paused")
            return {"status": "resumed"}
        except ValueError as e:
            raise HTTPException(status_code=400, detail=f"Invalid task ID: {e}") from e

    @app.post("/api/v1/tasks/{task_id}/cancel", tags=["tasks"])
    async def cancel_task(task_id: str, reason: str = "user requested") -> dict[str, Any]:
        """Cancel a task."""
        try:
            from orchestrator import get_orchestrator

            orch = get_orchestrator()
            result = await orch.cancel(UUID(task_id), reason)
            if not result:
                raise HTTPException(status_code=404, detail="Task not found")
            return {"status": "cancelled"}
        except ValueError as e:
            raise HTTPException(status_code=400, detail=f"Invalid task ID: {e}") from e

    # --- Agent endpoints ---

    @app.get("/api/v1/agents", tags=["agents"])
    async def list_agents() -> dict[str, Any]:
        """List all registered agents."""
        try:
            from services.agent_registry import get_agent_registry

            registry = get_agent_registry()
            summaries = registry.list_agents()
            return {
                "agents": [
                    {
                        "agent_id": s.agent_id,
                        "agent_type": s.agent_type,
                        "implementation_name": s.implementation_name,
                        "version": s.version,
                        "vendor": s.vendor,
                        "capabilities": s.capabilities,
                        "health": s.health.value,
                        "enabled": s.enabled,
                        "initialized": s.initialized,
                        "track_record": s.track_record,
                    }
                    for s in summaries
                ],
            }
        except RuntimeError:
            return {"agents": [], "error": "registry not initialized"}

    @app.get("/api/v1/agents/{agent_id}", tags=["agents"])
    async def get_agent(agent_id: str) -> dict[str, Any]:
        """Get agent details + manifest."""
        try:
            from services.agent_registry import get_agent_registry

            registry = get_agent_registry()
            if not registry.has(agent_id):
                raise HTTPException(status_code=404, detail="Agent not found")
            manifest = registry.get_manifest(agent_id)
            track_record = registry.get_track_record(agent_id)
            return {
                "agent_id": manifest.identity.agent_id,
                "agent_type": manifest.identity.agent_type.value,
                "implementation_name": manifest.identity.implementation_name,
                "version": manifest.identity.version,
                "vendor": manifest.identity.vendor,
                "capabilities": manifest.capability_namespaces(),
                "resource_requirements": manifest.resource_requirements.model_dump(),
                "permissions_required": [p.name for p in manifest.permissions_required],
                "track_record": track_record,
            }
        except RuntimeError:
            raise HTTPException(status_code=500, detail="Registry not initialized") from None

    @app.get("/api/v1/capabilities", tags=["agents"])
    async def list_capabilities() -> dict[str, Any]:
        """List all capability namespaces indexed by the registry."""
        try:
            from services.agent_registry import get_agent_registry

            registry = get_agent_registry()
            return {"capabilities": registry.list_capabilities()}
        except RuntimeError:
            return {"capabilities": [], "error": "registry not initialized"}

    # --- Memory endpoints ---

    @app.post("/api/v1/memory/remember", tags=["memory"])
    async def memory_remember(req: MemoryRememberRequest) -> dict[str, Any]:
        """Store an item in memory."""
        try:
            from services.memory import get_memory_manager

            mgr = get_memory_manager()
            scope = MemoryScope(
                scope_type=MemoryScopeType(req.scope_type),
                project_id=req.project_id,
            )
            item = await mgr.remember(
                scope,
                req.content,
                content_type=req.content_type,
                metadata=req.metadata,
            )
            return {"item_id": str(item.id), "scope": str(scope), "created": True}
        except RuntimeError:
            raise HTTPException(status_code=500, detail="Memory manager not initialized") from None
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e

    @app.post("/api/v1/memory/recall", response_model=MemoryRecallResponse, tags=["memory"])
    async def memory_recall(req: MemoryRecallRequest) -> MemoryRecallResponse:
        """Recall items from memory (hybrid vector + graph + keyword search)."""
        try:
            from services.memory import get_memory_manager

            mgr = get_memory_manager()
            scope = None
            if req.scope_type:
                scope = MemoryScope(
                    scope_type=MemoryScopeType(req.scope_type),
                    project_id=req.project_id,
                )
            result = await mgr.recall(scope, req.query, k=req.k)
            return MemoryRecallResponse(
                items=[
                    {
                        "item_id": str(r.item.id),
                        "content": r.item.content[:500],
                        "score": round(r.score, 4),
                        "source": r.source,
                        "score_breakdown": r.score_breakdown,
                        "created_at": r.item.created_at.isoformat(),
                    }
                    for r in result.items
                ],
                total_found=result.total_found,
                elapsed_s=round(result.elapsed_s, 4),
            )
        except RuntimeError:
            raise HTTPException(status_code=500, detail="Memory manager not initialized") from None

    # --- Plugin endpoints ---

    @app.get("/api/v1/plugins", tags=["plugins"])
    async def list_plugins() -> dict[str, Any]:
        """List all plugins."""
        return {"plugins": [], "note": "Plugin manager not initialized via API"}

    @app.post("/api/v1/plugins/{name}/enable", tags=["plugins"])
    async def enable_plugin(name: str) -> dict[str, Any]:
        """Enable a plugin."""
        return {"name": name, "status": "not_implemented"}

    @app.post("/api/v1/plugins/{name}/disable", tags=["plugins"])
    async def disable_plugin(name: str) -> dict[str, Any]:
        """Disable a plugin."""
        return {"name": name, "status": "not_implemented"}

    # --- Provider endpoints ---

    @app.get("/api/v1/providers", tags=["providers"])
    async def list_providers() -> dict[str, Any]:
        """List all LLM providers."""
        try:
            from services.model_router import get_model_router

            router = get_model_router()
            healths = router.list_providers()
            return {
                "providers": [
                    {
                        "provider": h.provider,
                        "status": h.status.value,
                        "success_rate": round(h.success_rate, 4),
                        "avg_latency_s": round(h.avg_latency_s, 4),
                        "consecutive_failures": h.consecutive_failures,
                        "last_error": h.last_error,
                    }
                    for h in healths
                ],
            }
        except RuntimeError:
            return {"providers": [], "error": "model router not initialized"}

    @app.get("/api/v1/models", tags=["providers"])
    async def list_models(provider: str | None = None) -> dict[str, Any]:
        """List available models (optionally filtered by provider)."""
        try:
            from services.model_router import get_model_router

            router = get_model_router()
            models = await router.list_models(provider)
            return {
                "models": [
                    {
                        "name": m.name,
                        "display_name": m.display_name,
                        "provider": m.provider,
                        "supports_vision": m.supports_vision,
                        "supports_tools": m.supports_tools,
                        "supports_reasoning": m.supports_reasoning,
                        "context_window": m.context_window,
                        "cost_per_1m_input_usd": m.cost_per_1m_input_usd,
                        "cost_per_1m_output_usd": m.cost_per_1m_output_usd,
                    }
                    for m in models
                ],
            }
        except RuntimeError:
            return {"models": [], "error": "model router not initialized"}

    @app.get("/api/v1/costs", tags=["providers"])
    async def get_costs() -> dict[str, Any]:
        """Get cost summary."""
        try:
            from services.model_router import get_model_router

            router = get_model_router()
            return {
                "total_cost_usd": round(router.cost_ledger.get_total_cost(), 6),
                "by_provider": {
                    k: round(v, 6)
                    for k, v in router.cost_ledger.get_cost_by_provider().items()  # type: ignore[union-attr]
                },
            }
        except RuntimeError:
            return {"total_cost_usd": 0.0, "by_provider": {}}

    # --- Audit endpoints ---

    @app.get("/api/v1/audit", tags=["audit"])
    async def get_audit_log(
        actor_id: str | None = None,
        action: str | None = None,
        limit: int = 100,
    ) -> dict[str, Any]:
        """Query the audit log."""
        try:
            from services.security import get_security_manager

            mgr = get_security_manager()
            entries = await mgr.get_audit_entries(
                actor_id=actor_id,
                action=action,
                limit=limit,
            )
            return {
                "entries": [
                    {
                        "timestamp": e.timestamp.isoformat(),
                        "actor": str(e.actor),
                        "action": e.action,
                        "target": e.target,
                        "success": e.success,
                        "reason": e.reason,
                        "hash": e.hash[:16] + "...",
                    }
                    for e in entries
                ],
                "count": len(entries),
            }
        except RuntimeError:
            return {"entries": [], "error": "security manager not initialized"}

    @app.get("/api/v1/audit/verify", tags=["audit"])
    async def verify_audit_chain() -> dict[str, Any]:
        """Verify the audit log hash chain."""
        try:
            from services.security import get_security_manager

            mgr = get_security_manager()
            valid = await mgr.verify_audit_chain()
            return {"chain_valid": valid}
        except RuntimeError:
            return {"chain_valid": False, "error": "security manager not initialized"}

    # --- Approval endpoints ---

    @app.get("/api/v1/approvals", tags=["approvals"])
    async def list_pending_approvals() -> dict[str, Any]:
        """List pending approval gates."""
        # Phase 12: the approval gate manager isn't wired to the API yet
        return {"approvals": []}

    @app.post("/api/v1/approvals/{approval_id}/respond", tags=["approvals"])
    async def respond_to_approval(approval_id: str, req: ApprovalRespondRequest) -> dict[str, Any]:
        """Respond to a pending approval."""
        return {"approval_id": approval_id, "status": "not_implemented"}

    # --- WebSocket endpoints ---

    @app.websocket("/ws/events")
    async def ws_events(websocket: WebSocket) -> None:
        """Live event stream (WebSocket)."""
        await websocket.accept()
        try:
            from core.event_bus import get_bus

            bus = get_bus()

            # Subscribe to all events
            event_queue: asyncio.Queue[Any] = asyncio.Queue()

            async def on_event(event: Any) -> None:
                await event_queue.put(event)

            bus.subscribe("*", on_event, name="ws_events")

            while True:
                event = await event_queue.get()
                await websocket.send_json(
                    {
                        "id": str(event.id),
                        "topic": event.topic,
                        "timestamp": event.timestamp.isoformat(),
                        "correlation_id": str(event.correlation_id),
                        "payload": event.payload,
                    }
                )
        except WebSocketDisconnect:
            pass
        except RuntimeError:
            await websocket.send_json({"error": "event bus not initialized"})
            await websocket.close()

    @app.websocket("/ws/logs")
    async def ws_logs(websocket: WebSocket) -> None:
        """Live log stream (WebSocket)."""
        await websocket.accept()
        # Phase 12: log streaming would require a log handler that pushes to a queue
        # For now, send a heartbeat
        try:
            while True:
                await websocket.send_json(
                    {"type": "heartbeat", "timestamp": datetime.now(UTC).isoformat()}
                )
                await asyncio.sleep(30)
        except WebSocketDisconnect:
            pass

    # --- Dashboard endpoints (v2.0) ---

    # Lazy singletons for the dashboard service
    _workflow_store: WorkflowStore | None = None
    _metrics_collector: MetricsCollector | None = None
    _analytics: Analytics | None = None

    def _get_workflow_store() -> WorkflowStore:
        nonlocal _workflow_store
        if _workflow_store is None:
            _workflow_store = WorkflowStore()
        return _workflow_store

    def _get_metrics_collector() -> MetricsCollector:
        nonlocal _metrics_collector
        if _metrics_collector is None:
            _metrics_collector = MetricsCollector()
            # Try to subscribe to the global event bus, if initialized
            try:
                from core.event_bus import get_bus

                bus = get_bus()
                # Subscribe in a background task (subscribe is async)
                asyncio.create_task(_metrics_collector.subscribe(bus))
            except RuntimeError:
                pass  # bus not initialized — collector works in manual mode
        return _metrics_collector

    def _get_analytics() -> Analytics:
        nonlocal _analytics
        if _analytics is None:
            _analytics = Analytics(_get_metrics_collector())
        return _analytics

    @app.get("/api/v1/workflows", tags=["dashboard"])
    async def list_workflows() -> dict[str, Any]:
        """List all saved workflows."""
        store = _get_workflow_store()
        workflows = await store.list()
        return {
            "workflows": [w.to_dict() for w in workflows],
            "count": len(workflows),
        }

    @app.post("/api/v1/workflows", tags=["dashboard"])
    async def create_workflow(req: WorkflowCreateRequest) -> dict[str, Any]:
        """Create a new workflow."""
        store = _get_workflow_store()
        try:
            nodes = [WorkflowNode.from_dict(n) for n in req.nodes]
            edges = [WorkflowEdge.from_dict(e) for e in req.edges]
            wf = await store.create(
                name=req.name,
                description=req.description,
                nodes=nodes,
                edges=edges,
                tags=req.tags,
            )
            return wf.to_dict()
        except WorkflowValidationError as e:
            raise HTTPException(status_code=422, detail=str(e)) from e

    @app.get("/api/v1/workflows/{workflow_id}", tags=["dashboard"])
    async def get_workflow(workflow_id: str) -> dict[str, Any]:
        """Get a workflow by ID."""
        store = _get_workflow_store()
        try:
            wf = await store.get(workflow_id)
            return wf.to_dict()
        except WorkflowNotFoundError as e:
            raise HTTPException(status_code=404, detail=str(e)) from e

    @app.put("/api/v1/workflows/{workflow_id}", tags=["dashboard"])
    async def update_workflow(
        workflow_id: str,
        req: WorkflowUpdateRequest,
    ) -> dict[str, Any]:
        """Update a workflow."""
        store = _get_workflow_store()
        try:
            changes: dict[str, Any] = {}
            if req.name is not None:
                changes["name"] = req.name
            if req.description is not None:
                changes["description"] = req.description
            if req.nodes is not None:
                changes["nodes"] = [WorkflowNode.from_dict(n) for n in req.nodes]
            if req.edges is not None:
                changes["edges"] = [WorkflowEdge.from_dict(e) for e in req.edges]
            if req.tags is not None:
                changes["tags"] = req.tags
            wf = await store.update(workflow_id, changes)
            return wf.to_dict()
        except WorkflowNotFoundError as e:
            raise HTTPException(status_code=404, detail=str(e)) from e
        except WorkflowValidationError as e:
            raise HTTPException(status_code=422, detail=str(e)) from e

    @app.delete("/api/v1/workflows/{workflow_id}", tags=["dashboard"])
    async def delete_workflow(workflow_id: str) -> dict[str, Any]:
        """Delete a workflow."""
        store = _get_workflow_store()
        deleted = await store.delete(workflow_id)
        return {"deleted": deleted}

    @app.get("/api/v1/monitor/snapshot", tags=["dashboard"])
    async def monitor_snapshot() -> dict[str, Any]:
        """Get a live monitoring snapshot."""
        collector = _get_metrics_collector()
        snap = await collector.snapshot()
        return snap.to_dict()

    @app.get("/api/v1/monitor/timeseries", tags=["dashboard"])
    async def monitor_timeseries(
        metric: str = "event_count",
        window_minutes: int = 60,
    ) -> dict[str, Any]:
        """Get a time series for a specific metric."""
        collector = _get_metrics_collector()
        series = await collector.timeseries(
            metric=metric,
            window_minutes=window_minutes,
        )
        return {"metric": metric, "window_minutes": window_minutes, "series": series}

    @app.get("/api/v1/analytics/summary", tags=["dashboard"])
    async def analytics_summary() -> dict[str, Any]:
        """Get a summary of analytics (last 60 minutes)."""
        return await _get_analytics().summary()

    @app.get("/api/v1/analytics/costs", tags=["dashboard"])
    async def analytics_costs(window_minutes: int = 60) -> dict[str, Any]:
        """Get cost breakdown by capability."""
        return await _get_analytics().cost_breakdown(window_minutes=window_minutes)

    @app.get("/api/v1/analytics/latency", tags=["dashboard"])
    async def analytics_latency(window_minutes: int = 60) -> dict[str, Any]:
        """Get latency percentiles."""
        return await _get_analytics().latency_percentiles(window_minutes=window_minutes)

    @app.get("/api/v1/analytics/throughput", tags=["dashboard"])
    async def analytics_throughput(window_minutes: int = 60) -> dict[str, Any]:
        """Get throughput time series (events per minute)."""
        series = await _get_analytics().throughput_series(window_minutes=window_minutes)
        return {"window_minutes": window_minutes, "series": series}

    @app.post("/api/v1/monitor/record", tags=["dashboard"])
    async def monitor_record(req: RecordEventRequest) -> dict[str, Any]:
        """Manually record a metric event (for testing or external integrations)."""
        from core.contracts.actor import ActorRef, ActorType
        from core.contracts.event import Event

        collector = _get_metrics_collector()
        event = Event(
            topic=req.topic,
            correlation_id=UUID(req.correlation_id) if req.correlation_id else uuid4(),
            actor=ActorRef(type=ActorType.SYSTEM, id="api"),
            payload=req.payload,
        )
        await collector.record_event(event)
        return {"recorded": True}

    return app
