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
from typing import Any, cast
from uuid import UUID, uuid4

from fastapi import Body, FastAPI, HTTPException, WebSocket, WebSocketDisconnect
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
# Request models for experience, mission, and execution endpoints
# (must be at module level so Pydantic can resolve them for the OpenAPI schema)
# ---------------------------------------------------------------------------


class ExperienceSearchRequest(BaseModel):
    """Request body for POST /api/v1/experience/search."""

    query: str
    search_type: str | None = None
    limit: int = Field(default=10, ge=1, le=100)


class ExperienceReplayRequest(BaseModel):
    """Request body for POST /api/v1/experience/{id}/replay."""

    mode: str = "dry_run"
    comparison_agent_id: str | None = None


class ExperienceRecordRequest(BaseModel):
    """Request body for POST /api/v1/experience."""

    task_id: str
    agent_id: str
    agent_type: str
    provider: str | None = None
    model: str | None = None
    capabilities: list[str] = Field(default_factory=list)
    goal: str = ""
    input_summary: str = ""
    output_summary: str = ""
    outcome: str = "success"
    success: bool = True
    execution_time_s: float = 0.0
    latency_s: float = 0.0
    cost_usd: float = 0.0
    reflection_score: float = 0.0
    qa_score: float = 0.0
    confidence: float = 0.0
    retries: int = 0
    failure_reason: str | None = None
    recovery_action: str | None = None
    workflow_id: str | None = None


class MissionCreateRequest(BaseModel):
    """Request body for POST /api/v1/missions."""

    title: str
    description: str = ""
    objectives: list[str] = Field(default_factory=list)
    deliverables: list[str] = Field(default_factory=list)
    priority: str = "normal"
    budget_total_usd: float = 0.0
    deadline: str | None = None
    owner: str | None = None
    tags: list[str] = Field(default_factory=list)
    decompose: bool = True
    decomposition_strategy: str = "objective_per_project"


class MissionUpdateRequest(BaseModel):
    """Request body for PUT /api/v1/missions/{id}."""

    title: str | None = None
    description: str | None = None
    priority: str | None = None
    deadline: str | None = None
    owner: str | None = None
    tags: list[str] | None = None
    budget_total_usd: float | None = None


class WBSNodeCreateRequest(BaseModel):
    """Request body for POST /api/v1/missions/{id}/wbs."""

    node_type: str = "task"
    title: str
    description: str = ""
    parent_id: str | None = None
    depends_on: list[str] = Field(default_factory=list)
    capabilities_required: list[str] = Field(default_factory=list)
    assigned_agent_id: str | None = None
    assigned_provider: str | None = None


class MissionSearchRequest(BaseModel):
    """Request body for POST /api/v1/missions/search."""

    query: str
    limit: int = Field(default=10, ge=1, le=100)


class ExecutionRunRequest(BaseModel):
    """Request body for POST /api/v1/execution."""

    domain: str = "terminal"
    action: str = ""
    parameters: dict[str, Any] = Field(default_factory=dict)
    description: str = ""
    requested_by: str = "api"
    priority: str = "normal"
    timeout_s: float = 120.0
    requires_approval: bool = False
    sandbox_enabled: bool = True
    tags: list[str] = Field(default_factory=list)


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
        version="5.3.2",
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
        return {"status": "ok", "version": "5.3.2", "timestamp": datetime.now(UTC).isoformat()}

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

    # --- Experience & Learning endpoints (v2.1) ---

    _learning_engine: Any = None

    def _get_learning_engine() -> Any:
        nonlocal _learning_engine
        if _learning_engine is None:
            from services.experience import LearningEngine
            _learning_engine = LearningEngine()
        return _learning_engine

    # ExperienceSearchRequest, ExperienceReplayRequest, ExperienceRecordRequest
    # are defined at module level (required for Pydantic OpenAPI schema generation).

    @app.get("/api/v1/experience", tags=["experience"])
    async def list_experiences(
        agent_id: str | None = None, provider: str | None = None,
        capability: str | None = None, outcome: str | None = None,
        success: bool | None = None, limit: int = 100, offset: int = 0,
    ) -> dict[str, Any]:
        from services.experience import ExperienceFilter
        engine = _get_learning_engine()
        filter = ExperienceFilter(agent_id=agent_id, provider=provider, capability=capability, outcome=outcome, success=success) if any([agent_id, provider, capability, outcome, success is not None]) else None
        records = await engine.list_experiences(filter, limit=limit, offset=offset)
        total = await engine.store.count(filter)
        return {"experiences": [r.to_dict() for r in records], "count": len(records), "total": total}

    @app.get("/api/v1/experience/{experience_id}", tags=["experience"])
    async def get_experience(experience_id: str) -> dict[str, Any]:
        engine = _get_learning_engine()
        try:
            record = await engine.get(UUID(experience_id))
            return cast("dict[str, Any]", record.to_dict())
        except Exception as e:
            raise HTTPException(status_code=404, detail=str(e)) from e

    @app.post("/api/v1/experience", tags=["experience"])
    async def record_experience(req: ExperienceRecordRequest) -> dict[str, Any]:
        from services.experience import ExperienceRecord
        engine = _get_learning_engine()
        record = ExperienceRecord(
            task_id=UUID(req.task_id), agent_id=req.agent_id, agent_type=req.agent_type,
            provider=req.provider, model=req.model, capabilities_used=req.capabilities,
            goal=req.goal, input_summary=req.input_summary, output_summary=req.output_summary,
            outcome=req.outcome, success=req.success, execution_time_s=req.execution_time_s,
            latency_s=req.latency_s, cost_usd=req.cost_usd, reflection_score=req.reflection_score,
            qa_score=req.qa_score, confidence=req.confidence, retries=req.retries,
            failure_reason=req.failure_reason, recovery_action=req.recovery_action,
            workflow_id=req.workflow_id,
        )
        stored = await engine.record(record)
        return cast("dict[str, Any]", stored.to_dict())

    @app.post("/api/v1/experience/search", tags=["experience"])
    async def search_experiences(req: ExperienceSearchRequest) -> dict[str, Any]:
        engine = _get_learning_engine()
        return cast("dict[str, Any]", await engine.search(req.query, search_type=req.search_type, limit=req.limit))
    @app.post("/api/v1/experience/{experience_id}/replay", tags=["experience"])
    async def replay_experience(experience_id: str, req: ExperienceReplayRequest) -> dict[str, Any]:
        engine = _get_learning_engine()
        result = await engine.replay(UUID(experience_id), mode=req.mode, comparison_agent_id=req.comparison_agent_id)
        return cast("dict[str, Any]", result.to_dict())

    @app.get("/api/v1/experience/export/{format}", tags=["experience"])
    async def export_experiences(format: str, agent_id: str | None = None, limit: int = 10000) -> dict[str, Any]:
        from services.experience import ExperienceFilter
        engine = _get_learning_engine()
        filter = ExperienceFilter(agent_id=agent_id) if agent_id else None
        if format == "csv":
            return {"format": "csv", "content": await engine.export_csv(filter, limit=limit)}
        return {"format": "json", "content": await engine.export_json(filter, limit=limit)}

    @app.get("/api/v1/learning/stats", tags=["learning"])
    async def learning_stats() -> dict[str, Any]:
        engine = _get_learning_engine()
        return cast("dict[str, Any]", (await engine.learning_stats()).to_dict())

    @app.get("/api/v1/learning/trends", tags=["learning"])
    async def learning_trends(days: int = 30, bucket: str = "day") -> dict[str, Any]:
        engine = _get_learning_engine()
        return {"days": days, "bucket": bucket, "series": await engine.trends(days=days, bucket=bucket)}

    @app.get("/api/v1/learning/agents", tags=["learning"])
    async def learning_agent_rankings(limit: int = 10) -> dict[str, Any]:
        engine = _get_learning_engine()
        return {"agents": await engine.rank_agents(limit=limit)}

    @app.get("/api/v1/learning/providers", tags=["learning"])
    async def learning_provider_rankings(limit: int = 10) -> dict[str, Any]:
        engine = _get_learning_engine()
        return {"providers": await engine.rank_providers(limit=limit)}

    @app.get("/api/v1/learning/workflows", tags=["learning"])
    async def learning_workflow_rankings(limit: int = 10) -> dict[str, Any]:
        engine = _get_learning_engine()
        return {"workflows": await engine.rank_workflows(limit=limit)}

    @app.get("/api/v1/learning/patterns", tags=["learning"])
    async def learning_patterns() -> dict[str, Any]:
        engine = _get_learning_engine()
        return cast("dict[str, Any]", (await engine.discover_patterns()).to_dict())

    @app.get("/api/v1/learning/recommendations/{capability}", tags=["learning"])
    async def recommend_agent(capability: str) -> dict[str, Any]:
        engine = _get_learning_engine()
        rec = await engine.recommend_agent_for_capability(capability)
        if rec is None:
            raise HTTPException(status_code=404, detail=f"No experience data for capability '{capability}'")
        return cast("dict[str, Any]", rec)

    # --- Mission & Organization endpoints (v3.0) ---

    _mission_manager: Any = None

    def _get_mission_manager() -> Any:
        nonlocal _mission_manager
        if _mission_manager is None:
            from services.organization import MissionManager
            _mission_manager = MissionManager()
        return _mission_manager

    # MissionCreateRequest, MissionUpdateRequest, WBSNodeCreateRequest, MissionSearchRequest
    # are defined at module level (required for Pydantic OpenAPI schema generation).

    @app.get("/api/v1/missions", tags=["missions"])
    async def list_missions(status: str | None = None, priority: str | None = None, owner: str | None = None, limit: int = 100, offset: int = 0) -> dict[str, Any]:
        from services.organization import MissionFilter
        mgr = _get_mission_manager()
        filter = MissionFilter(status=status, priority=priority, owner=owner) if any([status, priority, owner]) else None
        missions = await mgr.list_missions(filter, limit=limit, offset=offset)
        return {"missions": [m.to_dict() for m in missions], "count": len(missions)}

    @app.post("/api/v1/missions", tags=["missions"])
    async def create_mission(req: MissionCreateRequest) -> dict[str, Any]:
        from datetime import datetime
        mgr = _get_mission_manager()
        deadline = datetime.fromisoformat(req.deadline) if req.deadline else None
        mission = await mgr.create_mission(title=req.title, description=req.description, objectives=req.objectives, deliverables=req.deliverables, priority=req.priority, budget_total_usd=req.budget_total_usd, deadline=deadline, owner=req.owner, tags=req.tags, decompose=req.decompose, decomposition_strategy=req.decomposition_strategy)
        return cast("dict[str, Any]", mission.to_dict())

    @app.get("/api/v1/missions/{mission_id}", tags=["missions"])
    async def get_mission(mission_id: str) -> dict[str, Any]:
        mgr = _get_mission_manager()
        try:
            return cast("dict[str, Any]", (await mgr.get_mission(mission_id)).to_dict())
        except Exception as e:
            raise HTTPException(status_code=404, detail=str(e)) from e

    @app.patch("/api/v1/missions/{mission_id}", tags=["missions"])
    async def update_mission(mission_id: str, req: MissionUpdateRequest) -> dict[str, Any]:
        mgr = _get_mission_manager()
        changes: dict[str, Any] = {}
        if req.title is not None:
            changes["title"] = req.title
        if req.description is not None:
            changes["description"] = req.description
        if req.priority is not None:
            changes["priority"] = req.priority
        if req.deadline is not None:
            changes["deadline"] = req.deadline
        if req.owner is not None:
            changes["owner"] = req.owner
        if req.tags is not None:
            changes["tags"] = req.tags
        if req.budget_total_usd is not None:
            changes["budget_total_usd"] = req.budget_total_usd
        return cast("dict[str, Any]", (await mgr.update_mission(mission_id, changes)).to_dict())

    @app.delete("/api/v1/missions/{mission_id}", tags=["missions"])
    async def delete_mission(mission_id: str) -> dict[str, Any]:
        mgr = _get_mission_manager()
        return {"deleted": await mgr.delete_mission(mission_id)}

    @app.post("/api/v1/missions/{mission_id}/start", tags=["missions"])
    async def start_mission(mission_id: str) -> dict[str, Any]:
        mgr = _get_mission_manager()
        try:
            return cast("dict[str, Any]", (await mgr.start_mission(mission_id)).to_dict())
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e)) from e

    @app.post("/api/v1/missions/{mission_id}/pause", tags=["missions"])
    async def pause_mission(mission_id: str, reason: str = "") -> dict[str, Any]:
        mgr = _get_mission_manager()
        try:
            return cast("dict[str, Any]", (await mgr.pause_mission(mission_id, reason=reason)).to_dict())
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e)) from e

    @app.post("/api/v1/missions/{mission_id}/resume", tags=["missions"])
    async def resume_mission(mission_id: str) -> dict[str, Any]:
        mgr = _get_mission_manager()
        try:
            return cast("dict[str, Any]", (await mgr.resume_mission(mission_id)).to_dict())
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e)) from e

    @app.post("/api/v1/missions/{mission_id}/cancel", tags=["missions"])
    async def cancel_mission(mission_id: str, reason: str = "") -> dict[str, Any]:
        mgr = _get_mission_manager()
        try:
            return cast("dict[str, Any]", (await mgr.cancel_mission(mission_id, reason=reason)).to_dict())
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e)) from e

    @app.post("/api/v1/missions/{mission_id}/replay", tags=["missions"])
    async def replay_mission(mission_id: str) -> dict[str, Any]:
        mgr = _get_mission_manager()
        return cast("dict[str, Any]", (await mgr.replay_mission(mission_id)).to_dict())

    @app.get("/api/v1/missions/{mission_id}/timeline", tags=["missions"])
    async def mission_timeline(mission_id: str) -> dict[str, Any]:
        mgr = _get_mission_manager()
        timeline = await mgr.get_mission_timeline(mission_id)
        return {"mission_id": mission_id, "timeline": timeline, "count": len(timeline)}

    @app.get("/api/v1/missions/{mission_id}/analytics", tags=["missions"])
    async def mission_analytics_endpoint(mission_id: str) -> dict[str, Any]:
        mgr = _get_mission_manager()
        return cast("dict[str, Any]", await mgr.get_mission_analytics(mission_id))
    @app.get("/api/v1/missions/{mission_id}/artifacts", tags=["missions"])
    async def mission_artifacts(mission_id: str) -> dict[str, Any]:
        mgr = _get_mission_manager()
        mission = await mgr.get_mission(mission_id)
        return {"mission_id": mission_id, "artifacts": [a.to_dict() for a in mission.artifacts], "count": len(mission.artifacts)}

    @app.get("/api/v1/missions/{mission_id}/graph", tags=["missions"])
    async def mission_graph_endpoint(mission_id: str) -> dict[str, Any]:
        mgr = _get_mission_manager()
        return cast("dict[str, Any]", await mgr.get_mission_graph(mission_id))
    @app.post("/api/v1/missions/{mission_id}/wbs", tags=["missions"])
    async def add_wbs_node(mission_id: str, req: WBSNodeCreateRequest) -> dict[str, Any]:
        mgr = _get_mission_manager()
        node = await mgr.add_wbs_node(mission_id, req.node_type, title=req.title, description=req.description, parent_id=req.parent_id, depends_on=req.depends_on, capabilities_required=req.capabilities_required, assigned_agent_id=req.assigned_agent_id, assigned_provider=req.assigned_provider)
        return cast("dict[str, Any]", node.to_dict())

    @app.get("/api/v1/missions/{mission_id}/evaluate", tags=["missions"])
    async def evaluate_mission(mission_id: str) -> dict[str, Any]:
        mgr = _get_mission_manager()
        recs = await mgr.evaluate_mission(mission_id)
        return {"mission_id": mission_id, "recommendations": [r.to_dict() for r in recs], "count": len(recs)}

    @app.get("/api/v1/missions/portfolio/metrics", tags=["missions"])
    async def portfolio_metrics() -> dict[str, Any]:
        mgr = _get_mission_manager()
        return cast("dict[str, Any]", (await mgr.get_portfolio_metrics()).to_dict())

    @app.post("/api/v1/missions/search", tags=["missions"])
    async def search_missions(req: MissionSearchRequest) -> dict[str, Any]:
        mgr = _get_mission_manager()
        results = await mgr.search_missions(req.query, limit=req.limit)
        return {"results": results, "count": len(results)}

    # --- Intelligence endpoints (v3.1) ---

    _intelligence_manager: Any = None

    def _get_intelligence_manager() -> Any:
        nonlocal _intelligence_manager
        if _intelligence_manager is None:
            from services.intelligence import IntelligenceManager
            _intelligence_manager = IntelligenceManager()
        return _intelligence_manager

    @app.get("/api/v1/intelligence/health", tags=["intelligence"])
    async def intelligence_health() -> dict[str, Any]:
        """Get enterprise health score."""
        mgr = _get_intelligence_manager()
        health = await mgr.compute_health()
        return cast("dict[str, Any]", health.to_dict())

    @app.get("/api/v1/intelligence/forecast", tags=["intelligence"])
    async def intelligence_forecast() -> dict[str, Any]:
        """Get predictive forecasts."""
        mgr = _get_intelligence_manager()
        forecasts = await mgr.forecast()
        return {"forecasts": [f.to_dict() for f in forecasts], "count": len(forecasts)}

    @app.get("/api/v1/intelligence/optimization", tags=["intelligence"])
    async def intelligence_optimization() -> dict[str, Any]:
        """Get optimization recommendations."""
        mgr = _get_intelligence_manager()
        recs = await mgr.optimize()
        return {"recommendations": [r.to_dict() for r in recs], "count": len(recs)}

    @app.get("/api/v1/intelligence/risks", tags=["intelligence"])
    async def intelligence_risks() -> dict[str, Any]:
        """Get risk assessments + heat map."""
        mgr = _get_intelligence_manager()
        risks = await mgr.assess_risks()
        heat_map = mgr.risk.heat_map(risks)
        return {
            "risks": [r.to_dict() for r in risks],
            "count": len(risks),
            "heat_map": heat_map,
        }

    @app.get("/api/v1/intelligence/capacity", tags=["intelligence"])
    async def intelligence_capacity() -> dict[str, Any]:
        """Get capacity forecasts."""
        mgr = _get_intelligence_manager()
        caps = await mgr.forecast_capacity()
        return {"capacity": [c.to_dict() for c in caps], "count": len(caps)}

    @app.get("/api/v1/intelligence/reliability", tags=["intelligence"])
    async def intelligence_reliability() -> dict[str, Any]:
        """Get reliability metrics."""
        mgr = _get_intelligence_manager()
        metrics = await mgr.collect_metrics()
        health = await mgr.compute_health()
        return {
            "avg_agent_reliability": metrics.avg_agent_reliability,
            "avg_provider_reliability": metrics.avg_provider_reliability,
            "reliability_score": health.reliability,
            "agent_efficiency": health.agent_efficiency,
            "provider_efficiency": health.provider_efficiency,
        }

    @app.get("/api/v1/intelligence/quality", tags=["intelligence"])
    async def intelligence_quality() -> dict[str, Any]:
        """Get quality metrics."""
        mgr = _get_intelligence_manager()
        metrics = await mgr.collect_metrics()
        health = await mgr.compute_health()
        return {
            "workflow_quality": health.workflow_quality,
            "execution_success": health.execution_success,
            "innovation": health.innovation,
            "total_wbs_nodes": metrics.total_wbs_nodes,
            "completed_wbs_nodes": metrics.completed_wbs_nodes,
            "total_artifacts": metrics.total_artifacts,
        }

    @app.get("/api/v1/intelligence/cost", tags=["intelligence"])
    async def intelligence_cost() -> dict[str, Any]:
        """Get cost analysis + forecast."""
        mgr = _get_intelligence_manager()
        analysis = await mgr.analyze_cost()
        forecast = await mgr.forecast_cost()
        return {"analysis": analysis.to_dict(), "forecast": forecast.to_dict()}

    @app.get("/api/v1/intelligence/digital-twin", tags=["intelligence"])
    async def intelligence_digital_twin() -> dict[str, Any]:
        """Get digital twin snapshot."""
        mgr = _get_intelligence_manager()
        twin = await mgr.digital_twin_snapshot()
        return cast("dict[str, Any]", twin.to_dict())

    @app.get("/api/v1/intelligence/report/{report_type}", tags=["intelligence"])
    async def intelligence_report(report_type: str) -> dict[str, Any]:
        """Generate an intelligence report."""
        mgr = _get_intelligence_manager()
        report = await mgr.generate_report(report_type)
        return cast("dict[str, Any]", report.to_dict())

    @app.get("/api/v1/intelligence/all", tags=["intelligence"])
    async def intelligence_all() -> dict[str, Any]:
        """Get all intelligence data in one response."""
        mgr = _get_intelligence_manager()
        return cast("dict[str, Any]", await mgr.get_all_intelligence())
    # --- Execution endpoints (v4.0) ---

    _execution_manager: Any = None

    def _get_execution_manager() -> Any:
        nonlocal _execution_manager
        if _execution_manager is None:
            from services.execution import ExecutionManager
            _execution_manager = ExecutionManager()
        return _execution_manager

    # ExecutionRunRequest is defined at module level (required for Pydantic OpenAPI schema generation).

    @app.post("/api/v1/execution", tags=["execution"])
    async def create_execution(req: ExecutionRunRequest) -> dict[str, Any]:
        """Submit an execution request."""
        from services.execution import ExecutionPolicy, ExecutionRequest, SandboxConfig
        mgr = _get_execution_manager()
        request = ExecutionRequest(
            domain=req.domain,
            action=req.action,
            parameters=req.parameters,
            description=req.description,
            requested_by=req.requested_by,
            priority=req.priority,
            timeout_s=req.timeout_s,
            policy=ExecutionPolicy(
                requires_approval=req.requires_approval,
                sandbox_enabled=req.sandbox_enabled,
                sandbox_config=SandboxConfig(enabled=req.sandbox_enabled),
            ),
            tags=req.tags,
        )
        result = await mgr.execute(request)
        return cast("dict[str, Any]", result.to_dict())

    @app.get("/api/v1/execution", tags=["execution"])
    async def list_executions(
        domain: str | None = None,
        status: str | None = None,
        limit: int = 100,
    ) -> dict[str, Any]:
        """List executions with optional filtering."""
        mgr = _get_execution_manager()
        history = await mgr.get_history(domain=domain, status=status, limit=limit)
        return {"executions": history, "count": len(history)}

    @app.get("/api/v1/execution/{execution_id}", tags=["execution"])
    async def get_execution(execution_id: str) -> dict[str, Any]:
        """Get execution status + result."""
        mgr = _get_execution_manager()
        try:
            result = await mgr.get_status(execution_id)
            return cast("dict[str, Any]", result.to_dict())
        except Exception as e:
            raise HTTPException(status_code=404, detail=str(e)) from e

    @app.post("/api/v1/execution/{execution_id}/cancel", tags=["execution"])
    async def cancel_execution(execution_id: str, reason: str = "") -> dict[str, Any]:
        """Cancel an execution."""
        mgr = _get_execution_manager()
        try:
            result = await mgr.cancel(execution_id, reason=reason)
            return cast("dict[str, Any]", result.to_dict())
        except Exception as e:
            raise HTTPException(status_code=404, detail=str(e)) from e

    @app.post("/api/v1/execution/{execution_id}/approve", tags=["execution"])
    async def approve_execution(
        execution_id: str,
        decided_by: str = "operator",
        reason: str = "",
    ) -> dict[str, Any]:
        """Approve a pending execution."""
        mgr = _get_execution_manager()
        approvals = await mgr.get_pending_approvals()
        approval = next((a for a in approvals if a.execution_id == execution_id), None)
        if approval is None:
            raise HTTPException(status_code=404, detail="No pending approval for this execution")
        result = await mgr.approve(approval.approval_id, decided_by, reason)
        return result.to_dict() if result else {"error": "Approval not found"}

    @app.get("/api/v1/execution/{execution_id}/logs", tags=["execution"])
    async def get_execution_logs(execution_id: str) -> dict[str, Any]:
        """Get logs for an execution."""
        mgr = _get_execution_manager()
        try:
            logs = await mgr.get_logs(execution_id)
            return {"execution_id": execution_id, "logs": [log.to_dict() for log in logs], "count": len(logs)}
        except Exception as e:
            raise HTTPException(status_code=404, detail=str(e)) from e

    @app.get("/api/v1/execution/history", tags=["execution"])
    async def execution_history(
        domain: str | None = None,
        status: str | None = None,
        limit: int = 100,
    ) -> dict[str, Any]:
        """Get execution history."""
        mgr = _get_execution_manager()
        history = await mgr.get_history(domain=domain, status=status, limit=limit)
        return {"history": history, "count": len(history)}

    @app.get("/api/v1/execution/approvals/pending", tags=["execution"])
    async def pending_approvals() -> dict[str, Any]:
        """Get pending approval requests."""
        mgr = _get_execution_manager()
        approvals = await mgr.get_pending_approvals()
        return {"approvals": [a.to_dict() for a in approvals], "count": len(approvals)}

    @app.post("/api/v1/execution/{execution_id}/replay", tags=["execution"])
    async def replay_execution(execution_id: str) -> dict[str, Any]:
        """Replay an execution."""
        mgr = _get_execution_manager()
        try:
            result = await mgr.replay(execution_id)
            return cast("dict[str, Any]", result.to_dict())
        except Exception as e:
            raise HTTPException(status_code=404, detail=str(e)) from e

    @app.post("/api/v1/execution/{execution_id}/rollback", tags=["execution"])
    async def rollback_execution(execution_id: str) -> dict[str, Any]:
        """Rollback an execution."""
        mgr = _get_execution_manager()
        try:
            result = await mgr.rollback(execution_id)
            return cast("dict[str, Any]", result.to_dict())
        except Exception as e:
            raise HTTPException(status_code=404, detail=str(e)) from e

    @app.get("/api/v1/execution/audit/log", tags=["execution"])
    async def execution_audit_log(limit: int = 100) -> dict[str, Any]:
        """Get the execution audit log."""
        mgr = _get_execution_manager()
        entries = await mgr.get_audit_log(limit=limit)
        return {"entries": [e.to_dict() for e in entries], "count": len(entries)}

    # --- Cognitive Intelligence endpoints (v5.0) ---

    _cognitive_manager: Any = None

    def _get_cognitive_manager() -> Any:
        nonlocal _cognitive_manager
        if _cognitive_manager is None:
            from services.cognitive import CognitiveManager
            _cognitive_manager = CognitiveManager()
        return _cognitive_manager

    @app.get("/api/v1/cognitive/experience", tags=["cognitive"])
    async def cognitive_experience_stats() -> dict[str, Any]:
        """Get experience statistics."""
        mgr = _get_cognitive_manager()
        return cast("dict[str, Any]", await mgr.experience_stats())
    @app.get("/api/v1/cognitive/experience/timeline", tags=["cognitive"])
    async def cognitive_experience_timeline(limit: int = 50) -> dict[str, Any]:
        """Get experience timeline."""
        mgr = _get_cognitive_manager()
        return {"timeline": await mgr.experience_timeline(limit=limit)}

    @app.post("/api/v1/cognitive/experience/search", tags=["cognitive"])
    async def cognitive_experience_search(query: dict[str, Any]) -> dict[str, Any]:
        """Search experiences."""
        mgr = _get_cognitive_manager()
        results = await mgr.search_experiences(**query)
        return {"results": results, "count": len(results)}

    @app.get("/api/v1/cognitive/experience/export/{format}", tags=["cognitive"])
    async def cognitive_experience_export(format: str) -> dict[str, Any]:
        """Export experiences."""
        mgr = _get_cognitive_manager()
        content = await mgr.experience_export(format=format)
        return {"format": format, "content": content}

    @app.get("/api/v1/cognitive/learning", tags=["cognitive"])
    async def cognitive_learning() -> dict[str, Any]:
        """Get learning insights."""
        mgr = _get_cognitive_manager()
        insights = await mgr.learn()
        metrics = await mgr.learning_metrics()
        return {"insights": insights, "metrics": metrics}

    @app.post("/api/v1/cognitive/predict", tags=["cognitive"])
    async def cognitive_predict(context: dict[str, Any]) -> dict[str, Any]:
        """Generate predictions."""
        mgr = _get_cognitive_manager()
        predictions = await mgr.predict(context)
        return {"predictions": predictions, "count": len(predictions)}

    @app.get("/api/v1/cognitive/recommendations", tags=["cognitive"])
    async def cognitive_recommendations() -> dict[str, Any]:
        """Get optimization recommendations."""
        mgr = _get_cognitive_manager()
        recs = await mgr.optimize()
        return {"recommendations": recs, "count": len(recs)}

    @app.get("/api/v1/cognitive/knowledge-graph", tags=["cognitive"])
    async def cognitive_knowledge_graph() -> dict[str, Any]:
        """Get knowledge graph snapshot."""
        mgr = _get_cognitive_manager()
        return cast("dict[str, Any]", mgr.graph_snapshot())

    @app.get("/api/v1/cognitive/knowledge-graph/search", tags=["cognitive"])
    async def cognitive_kg_search(q: str) -> dict[str, Any]:
        """Search the knowledge graph."""
        mgr = _get_cognitive_manager()
        results = mgr.graph_search(q)
        return {"results": results, "count": len(results)}

    @app.get("/api/v1/cognitive/knowledge-graph/impact/{node_id}", tags=["cognitive"])
    async def cognitive_kg_impact(node_id: str) -> dict[str, Any]:
        """Impact analysis for a knowledge graph node."""
        mgr = _get_cognitive_manager()
        return cast("dict[str, Any]", mgr.graph_impact_analysis(node_id))

    @app.get("/api/v1/cognitive/architecture", tags=["cognitive"])
    async def cognitive_architecture() -> dict[str, Any]:
        """Get architecture intelligence."""
        mgr = _get_cognitive_manager()
        issues = await mgr.arch_analyze()
        return {"issues": issues, "count": len(issues)}

    @app.get("/api/v1/cognitive/repository-health", tags=["cognitive"])
    async def cognitive_repo_health() -> dict[str, Any]:
        """Get repository health report."""
        mgr = _get_cognitive_manager()
        return cast("dict[str, Any]", await mgr.repo_health())
    @app.get("/api/v1/cognitive/reports/{report_type}", tags=["cognitive"])
    async def cognitive_report(report_type: str) -> dict[str, Any]:
        """Generate a cognitive report."""
        mgr = _get_cognitive_manager()
        return cast("dict[str, Any]", await mgr.generate_report(report_type))
    @app.get("/api/v1/cognitive/reports/{report_type}/export/{format}", tags=["cognitive"])
    async def cognitive_report_export(report_type: str, format: str) -> dict[str, Any]:
        """Export a cognitive report."""
        mgr = _get_cognitive_manager()
        content = await mgr.export_report(report_type=report_type, format=format)
        return {"format": format, "content": content}

    @app.get("/api/v1/cognitive/all", tags=["cognitive"])
    async def cognitive_all() -> dict[str, Any]:
        """Get all cognitive data in one response."""
        mgr = _get_cognitive_manager()
        return cast("dict[str, Any]", await mgr.get_all())
    # --- Knowledge Platform endpoints (v5.1) ---

    _knowledge_platform: Any = None

    def _get_knowledge_platform() -> Any:
        nonlocal _knowledge_platform
        if _knowledge_platform is None:
            from services.knowledge import KnowledgePlatform
            _knowledge_platform = KnowledgePlatform()
        return _knowledge_platform

    @app.get("/api/v1/knowledge", tags=["knowledge"])
    async def knowledge_list(
        workspace_id: str | None = None,
        collection_id: str | None = None,
        status: str | None = None,
        limit: int = 100,
    ) -> dict[str, Any]:
        """List knowledge entries."""
        platform = _get_knowledge_platform()
        entries = await platform.list_entries(
            workspace_id=workspace_id, collection_id=collection_id,
            status=status, limit=limit,
        )
        return {"entries": [e.to_dict() for e in entries], "count": len(entries)}

    @app.post("/api/v1/knowledge", tags=["knowledge"])
    async def knowledge_create(body: dict[str, Any]) -> dict[str, Any]:
        """Create a knowledge entry."""
        from services.knowledge import KnowledgeEntry
        platform = _get_knowledge_platform()
        entry = KnowledgeEntry(**body)
        created = await platform.create_entry(entry)
        return cast("dict[str, Any]", created.to_dict())

    @app.get("/api/v1/knowledge/{entry_id}", tags=["knowledge"])
    async def knowledge_get(entry_id: str) -> dict[str, Any]:
        """Get a knowledge entry."""
        platform = _get_knowledge_platform()
        entry = await platform.get_entry(entry_id)
        if entry is None:
            raise HTTPException(status_code=404, detail="Entry not found")
        return cast("dict[str, Any]", entry.to_dict())

    @app.get("/api/v1/knowledge/{entry_id}/versions", tags=["knowledge"])
    async def knowledge_versions(entry_id: str) -> dict[str, Any]:
        """Get version history for a knowledge entry."""
        platform = _get_knowledge_platform()
        versions = await platform.get_versions(entry_id)
        return {"versions": [v.to_dict() for v in versions], "count": len(versions)}

    @app.post("/api/v1/knowledge/search", tags=["knowledge"])
    async def knowledge_search(body: dict[str, Any]) -> dict[str, Any]:
        """Search knowledge entries."""
        platform = _get_knowledge_platform()
        query = body.get("query", "")
        results = await platform.search(
            query,
            workspace_id=body.get("workspace_id"),
            collection_id=body.get("collection_id"),
            limit=body.get("limit", 10),
        )
        return {"results": results, "count": len(results)}

    @app.post("/api/v1/knowledge/rag", tags=["knowledge"])
    async def knowledge_rag(body: dict[str, Any]) -> dict[str, Any]:
        """RAG retrieval."""
        from services.knowledge import RetrievalRequest
        platform = _get_knowledge_platform()
        request = RetrievalRequest(
            query=body.get("query", ""),
            max_results=body.get("max_results", 10),
            workspace_id=body.get("workspace_id"),
            include_citations=body.get("include_citations", True),
        )
        return cast("dict[str, Any]", await platform.rag(request))
    @app.get("/api/v1/knowledge/graph", tags=["knowledge"])
    async def knowledge_graph() -> dict[str, Any]:
        """Get knowledge graph snapshot."""
        platform = _get_knowledge_platform()
        return cast("dict[str, Any]", await platform.graph_snapshot())
    @app.get("/api/v1/knowledge/graph/search", tags=["knowledge"])
    async def knowledge_graph_search(q: str) -> dict[str, Any]:
        """Search the knowledge graph."""
        platform = _get_knowledge_platform()
        results = await platform.graph_search(q)
        return {"results": results, "count": len(results)}

    @app.get("/api/v1/knowledge/graph/impact/{node_id}", tags=["knowledge"])
    async def knowledge_graph_impact(node_id: str) -> dict[str, Any]:
        """Impact analysis for a graph node."""
        platform = _get_knowledge_platform()
        return cast("dict[str, Any]", await platform.graph_impact(node_id))
    @app.get("/api/v1/knowledge/collections", tags=["knowledge"])
    async def knowledge_collections(workspace_id: str | None = None) -> dict[str, Any]:
        """List knowledge collections."""
        platform = _get_knowledge_platform()
        collections = await platform.list_collections(workspace_id)
        return {"collections": [c.to_dict() for c in collections], "count": len(collections)}

    @app.get("/api/v1/knowledge/workspaces", tags=["knowledge"])
    async def knowledge_workspaces() -> dict[str, Any]:
        """List knowledge workspaces."""
        platform = _get_knowledge_platform()
        workspaces = await platform.list_workspaces()
        return {"workspaces": [w.to_dict() for w in workspaces], "count": len(workspaces)}

    @app.get("/api/v1/knowledge/statistics", tags=["knowledge"])
    async def knowledge_stats() -> dict[str, Any]:
        """Get knowledge platform statistics."""
        platform = _get_knowledge_platform()
        return cast("dict[str, Any]", await platform.stats())
    @app.get("/api/v1/knowledge/memory", tags=["knowledge"])
    async def knowledge_memory_stats() -> dict[str, Any]:
        """Get memory platform statistics."""
        platform = _get_knowledge_platform()
        return cast("dict[str, Any]", await platform.memory_stats())
    @app.post("/api/v1/knowledge/memory", tags=["knowledge"])
    async def knowledge_memory_store(body: dict[str, Any]) -> dict[str, Any]:
        """Store a memory record."""
        from services.knowledge import MemoryRecord
        platform = _get_knowledge_platform()
        record = MemoryRecord(**body)
        stored = await platform.store_memory(record)
        return cast("dict[str, Any]", stored.to_dict())

    @app.post("/api/v1/knowledge/memory/search", tags=["knowledge"])
    async def knowledge_memory_search(body: dict[str, Any]) -> dict[str, Any]:
        """Search memory records."""
        platform = _get_knowledge_platform()
        results = await platform.search_memory(
            body.get("query", ""),
            memory_types=body.get("memory_types"),
            tags=body.get("tags"),
            limit=body.get("limit", 50),
        )
        return {"results": results, "count": len(results)}

    # --- Knowledge Intelligence endpoints (v5.1 Part 2) ---

    _knowledge_intelligence: Any = None
    _autonomous_learning: Any = None
    _recommendation_engine: Any = None
    _repo_intelligence: Any = None
    _document_intelligence: Any = None
    _quality_assurance: Any = None

    def _get_knowledge_intelligence() -> Any:
        nonlocal _knowledge_intelligence
        if _knowledge_intelligence is None:
            from services.knowledge import KnowledgeIntelligenceEngine
            _knowledge_intelligence = KnowledgeIntelligenceEngine()
        return _knowledge_intelligence

    def _get_autonomous_learning() -> Any:
        nonlocal _autonomous_learning
        if _autonomous_learning is None:
            from services.knowledge import AutonomousLearningEngine
            _autonomous_learning = AutonomousLearningEngine()
        return _autonomous_learning

    def _get_recommendation_engine() -> Any:
        nonlocal _recommendation_engine
        if _recommendation_engine is None:
            from services.knowledge import RecommendationEngine
            _recommendation_engine = RecommendationEngine(_get_autonomous_learning())
        return _recommendation_engine

    def _get_repo_intelligence() -> Any:
        nonlocal _repo_intelligence
        if _repo_intelligence is None:
            from pathlib import Path

            from services.knowledge import RepositoryIntelligenceEngine
            _repo_intelligence = RepositoryIntelligenceEngine(Path())
        return _repo_intelligence

    def _get_document_intelligence() -> Any:
        nonlocal _document_intelligence
        if _document_intelligence is None:
            from services.knowledge import DocumentIntelligence
            _document_intelligence = DocumentIntelligence()
        return _document_intelligence

    def _get_quality_assurance() -> Any:
        nonlocal _quality_assurance
        if _quality_assurance is None:
            from services.knowledge import QualityAssurance
            _quality_assurance = QualityAssurance()
        return _quality_assurance

    @app.get("/api/v1/knowledge/quality", tags=["knowledge"])
    async def knowledge_quality() -> dict[str, Any]:
        """Get knowledge quality report."""
        platform = _get_knowledge_platform()
        entries = await platform.list_entries(limit=1000)
        engine = _get_knowledge_intelligence()
        await engine.ingest_entries(entries)
        report = await engine.quality_report()
        return cast("dict[str, Any]", report.to_dict())

    @app.get("/api/v1/knowledge/insights", tags=["knowledge"])
    async def knowledge_insights() -> dict[str, Any]:
        """Get knowledge intelligence insights."""
        platform = _get_knowledge_platform()
        entries = await platform.list_entries(limit=1000)
        engine = _get_knowledge_intelligence()
        await engine.ingest_entries(entries)
        insights = await engine.analyze_all()
        return {"insights": [i.to_dict() for i in insights], "count": len(insights)}

    @app.post("/api/v1/knowledge/learn", tags=["knowledge"])
    async def knowledge_learn(body: dict[str, Any]) -> dict[str, Any]:
        """Learn from an execution."""
        engine = _get_autonomous_learning()
        lesson = await engine.learn_from_execution(
            goal=body.get("goal", ""),
            success=body.get("success", True),
            agent_id=body.get("agent_id", ""),
            provider=body.get("provider", ""),
            duration_s=body.get("duration_s", 0.0),
            cost_usd=body.get("cost_usd", 0.0),
            error=body.get("error"),
            retries=body.get("retries", 0),
            feedback=body.get("feedback"),
        )
        return cast("dict[str, Any]", lesson.to_dict())

    @app.get("/api/v1/knowledge/lessons", tags=["knowledge"])
    async def knowledge_lessons(
        category: str | None = None,
        limit: int = 50,
    ) -> dict[str, Any]:
        """Get lessons learned."""
        engine = _get_autonomous_learning()
        lessons = await engine.get_lessons(category=category, limit=limit)
        return {"lessons": [lesson.to_dict() for lesson in lessons], "count": len(lessons)}

    @app.get("/api/v1/knowledge/playbooks", tags=["knowledge"])
    async def knowledge_playbooks(limit: int = 20) -> dict[str, Any]:
        """Get playbooks."""
        engine = _get_autonomous_learning()
        playbooks = await engine.get_playbooks(limit=limit)
        return {"playbooks": [p.to_dict() for p in playbooks], "count": len(playbooks)}

    @app.post("/api/v1/knowledge/recommend", tags=["knowledge"])
    async def knowledge_recommend(body: dict[str, Any]) -> dict[str, Any]:
        """Get knowledge recommendations."""
        platform = _get_knowledge_platform()
        entries = await platform.list_entries(limit=500)
        memories = await platform.memory.search(limit=500)
        rec_engine = _get_recommendation_engine()
        await rec_engine.ingest(entries, memories)
        context = body.get("context", body.get("query", ""))
        recs = await rec_engine.recommend_all(context)
        return {"recommendations": recs, "count": len(recs)}

    @app.get("/api/v1/knowledge/learning/stats", tags=["knowledge"])
    async def knowledge_learning_stats() -> dict[str, Any]:
        """Get learning statistics."""
        engine = _get_autonomous_learning()
        return cast("dict[str, Any]", await engine.stats())
    @app.get("/api/v1/repository/analyze", tags=["repository"])
    async def repository_analyze() -> dict[str, Any]:
        """Analyze the repository."""
        engine = _get_repo_intelligence()
        analysis = await engine.analyze()
        return cast("dict[str, Any]", analysis.to_dict())

    @app.get("/api/v1/repository/health", tags=["repository"])
    async def repository_health() -> dict[str, Any]:
        """Get repository health."""
        engine = _get_repo_intelligence()
        analysis = await engine.analyze()
        return {
            "health_score": analysis.health_score,
            "total_files": analysis.total_files,
            "total_lines": analysis.total_lines,
            "total_classes": analysis.total_classes,
            "total_functions": analysis.total_functions,
            "total_tests": analysis.total_tests,
            "issue_count": len(analysis.issues),
        }

    @app.post("/api/v1/knowledge/document/analyze", tags=["knowledge"])
    async def document_analyze(body: dict[str, Any]) -> dict[str, Any]:
        """Analyze a document."""
        engine = _get_document_intelligence()
        result = await engine.analyze(
            body.get("file_path", ""),
            body.get("content", ""),
        )
        return cast("dict[str, Any]", result.to_dict())

    @app.get("/api/v1/knowledge/validate", tags=["knowledge"])
    async def knowledge_validate() -> dict[str, Any]:
        """Validate knowledge quality."""
        platform = _get_knowledge_platform()
        entries = await platform.list_entries(limit=1000)
        qa = _get_quality_assurance()
        issues = await qa.validate(entries)
        suggestions = await qa.repair_suggestions(issues)
        return {
            "issues": [i.to_dict() for i in issues],
            "suggestions": suggestions,
            "issue_count": len(issues),
        }

    # --- Engineering Intelligence endpoints (v5.2) ---

    _engineering_manager: Any = None

    def _get_engineering_manager() -> Any:
        nonlocal _engineering_manager
        if _engineering_manager is None:
            from services.engineering import EngineeringManager
            _engineering_manager = EngineeringManager()
        return _engineering_manager

    @app.get("/api/v1/engineering/repository/analyze", tags=["engineering"])
    async def engineering_repo_analyze() -> dict[str, Any]:
        """Analyze the repository."""
        mgr = _get_engineering_manager()
        return cast("dict[str, Any]", await mgr.analyze_repository())
    @app.get("/api/v1/engineering/repository/discover", tags=["engineering"])
    async def engineering_repo_discover() -> dict[str, Any]:
        """Discover repositories."""
        mgr = _get_engineering_manager()
        repos = await mgr.discover_repositories()
        return {"repositories": repos, "count": len(repos)}

    @app.post("/api/v1/engineering/code/analyze", tags=["engineering"])
    async def engineering_code_analyze(body: dict[str, Any]) -> dict[str, Any]:
        """Analyze a source file."""
        mgr = _get_engineering_manager()
        return cast("dict[str, Any]", await mgr.analyze_file(body.get("file_path", "")))

    @app.get("/api/v1/engineering/architecture/recommendations", tags=["engineering"])
    async def engineering_arch_recs() -> dict[str, Any]:
        """Get architecture recommendations."""
        mgr = _get_engineering_manager()
        recs = await mgr.architecture_recommendations()
        return {"recommendations": recs, "count": len(recs)}

    @app.get("/api/v1/engineering/agents", tags=["engineering"])
    async def engineering_agents() -> dict[str, Any]:
        """List engineering agents."""
        mgr = _get_engineering_manager()
        agents = mgr.list_engineering_agents()
        return {"agents": agents, "count": len(agents)}

    @app.get("/api/v1/engineering/agents/{agent_id}", tags=["engineering"])
    async def engineering_agent_detail(agent_id: str) -> dict[str, Any]:
        """Get an engineering agent by ID."""
        mgr = _get_engineering_manager()
        agent = mgr.get_engineering_agent(agent_id)
        if agent is None:
            raise HTTPException(status_code=404, detail="Agent not found")
        return cast("dict[str, Any]", agent)

    @app.post("/api/v1/engineering/agents/select", tags=["engineering"])
    async def engineering_agent_select(body: dict[str, Any]) -> dict[str, Any]:
        """Select the best agent for a task."""
        mgr = _get_engineering_manager()
        agent = mgr.select_agent_for_task(
            language=body.get("language"),
            framework=body.get("framework"),
            agent_type=body.get("agent_type"),
        )
        if agent is None:
            raise HTTPException(status_code=404, detail="No matching agent found")
        return cast("dict[str, Any]", agent)

    @app.get("/api/v1/engineering/capabilities", tags=["engineering"])
    async def engineering_capabilities() -> dict[str, Any]:
        """List capabilities."""
        mgr = _get_engineering_manager()
        caps = await mgr.list_capabilities()
        return {"capabilities": caps, "count": len(caps)}

    @app.get("/api/v1/engineering/capabilities/stats", tags=["engineering"])
    async def engineering_cap_stats() -> dict[str, Any]:
        """Get capability statistics."""
        mgr = _get_engineering_manager()
        return cast("dict[str, Any]", await mgr.capability_stats())
    @app.get("/api/v1/engineering/workspaces", tags=["engineering"])
    async def engineering_workspaces() -> dict[str, Any]:
        """List engineering workspaces."""
        mgr = _get_engineering_manager()
        workspaces = await mgr.list_workspaces()
        return {"workspaces": workspaces, "count": len(workspaces)}

    @app.post("/api/v1/engineering/workspaces", tags=["engineering"])
    async def engineering_create_workspace(body: dict[str, Any]) -> dict[str, Any]:
        """Create an engineering workspace."""
        mgr = _get_engineering_manager()
        return cast("dict[str, Any]", await mgr.create_workspace(
            body.get("name", ""),
            body.get("repo_paths", []),
        ))

    @app.get("/api/v1/engineering/overview", tags=["engineering"])
    async def engineering_overview() -> dict[str, Any]:
        """Get engineering overview."""
        mgr = _get_engineering_manager()
        return cast("dict[str, Any]", await mgr.get_overview())
    # --- Engineering Intelligence endpoints (v5.2 Part 1B-1) ---

    _planning_engine: Any = None
    _metrics_engine: Any = None
    _arch_analysis_engine: Any = None
    _impact_analysis_engine: Any = None
    _eng_recommendation_engine: Any = None
    _risk_engine: Any = None

    def _get_planning_engine() -> Any:
        nonlocal _planning_engine
        if _planning_engine is None:
            from services.engineering import PlanningEngine
            _planning_engine = PlanningEngine()
        return _planning_engine

    def _get_metrics_engine() -> Any:
        nonlocal _metrics_engine
        if _metrics_engine is None:
            from services.engineering import MetricsEngine
            _metrics_engine = MetricsEngine()
        return _metrics_engine

    def _get_arch_analysis() -> Any:
        nonlocal _arch_analysis_engine
        if _arch_analysis_engine is None:
            from services.engineering.intelligence import ArchitectureAnalysisEngine
            _arch_analysis_engine = ArchitectureAnalysisEngine()
        return _arch_analysis_engine

    def _get_impact_analysis() -> Any:
        nonlocal _impact_analysis_engine
        if _impact_analysis_engine is None:
            from services.engineering.intelligence import ImpactAnalysisEngine
            _impact_analysis_engine = ImpactAnalysisEngine()
        return _impact_analysis_engine

    def _get_eng_rec_engine() -> Any:
        nonlocal _eng_recommendation_engine
        if _eng_recommendation_engine is None:
            from services.engineering.intelligence import RecommendationEngine
            _eng_recommendation_engine = RecommendationEngine()
        return _eng_recommendation_engine

    def _get_risk_engine() -> Any:
        nonlocal _risk_engine
        if _risk_engine is None:
            from services.engineering import RiskEngine
            _risk_engine = RiskEngine()
        return _risk_engine

    @app.post("/api/v1/engineering/plan", tags=["engineering"])
    async def engineering_plan(body: dict[str, Any]) -> dict[str, Any]:
        """Create an engineering plan."""
        engine = _get_planning_engine()
        plan = await engine.create_plan(
            title=body.get("title", ""),
            description=body.get("description", ""),
            requirements=body.get("requirements", []),
            max_hours=body.get("max_hours", 100.0),
        )
        return cast("dict[str, Any]", plan.to_dict())

    @app.get("/api/v1/engineering/metrics", tags=["engineering"])
    async def engineering_metrics() -> dict[str, Any]:
        """Get engineering metrics."""
        from pathlib import Path
        engine = _get_metrics_engine()
        metrics = await engine.compute_metrics(Path())
        return cast("dict[str, Any]", metrics.to_dict())

    @app.get("/api/v1/engineering/architecture/analysis", tags=["engineering"])
    async def engineering_arch_analysis() -> dict[str, Any]:
        """Get architecture analysis."""
        from pathlib import Path
        engine = _get_arch_analysis()
        result = await engine.analyze(Path())
        return cast("dict[str, Any]", result.to_dict())

    @app.post("/api/v1/engineering/impact", tags=["engineering"])
    async def engineering_impact(body: dict[str, Any]) -> dict[str, Any]:
        """Analyze impact of a change."""
        from pathlib import Path
        engine = _get_impact_analysis()
        result = await engine.analyze_impact(
            Path(),
            body.get("target_file", ""),
            body.get("change_description", ""),
        )
        return cast("dict[str, Any]", result.to_dict())

    @app.get("/api/v1/engineering/recommendations", tags=["engineering"])
    async def engineering_recommendations() -> dict[str, Any]:
        """Get engineering recommendations."""
        from pathlib import Path
        metrics_engine = _get_metrics_engine()
        arch_engine = _get_arch_analysis()
        rec_engine = _get_eng_rec_engine()
        metrics = await metrics_engine.compute_metrics(Path())
        arch = await arch_engine.analyze(Path())
        recs = await rec_engine.recommend_all(metrics, arch)
        return {"recommendations": [r.to_dict() for r in recs], "count": len(recs)}

    @app.get("/api/v1/engineering/risks", tags=["engineering"])
    async def engineering_risks() -> dict[str, Any]:
        """Get engineering risk assessment."""
        from pathlib import Path
        metrics_engine = _get_metrics_engine()
        arch_engine = _get_arch_analysis()
        risk_engine = _get_risk_engine()
        metrics = await metrics_engine.compute_metrics(Path())
        arch = await arch_engine.analyze(Path())
        risks = await risk_engine.assess_all(metrics, arch)
        return {"risks": [r.to_dict() for r in risks], "count": len(risks)}

    # ------------------------------------------------------------------
    # Phase 26 — Engineering API Integration (Review, Test Intel, Docs,
    # Evolution, Release Readiness, Productivity, Health Center)
    # ------------------------------------------------------------------

    # --- Reviews (Phase 17) ---

    @app.post("/api/v1/engineering/reviews", tags=["engineering"])
    async def engineering_review_all(body: dict[str, Any] = Body({})) -> dict[str, Any]:
        """Run all 12 review types against the target."""
        target = body.get("target", ".")
        mgr = _get_engineering_manager()
        return cast("dict[str, Any]", await mgr.review_all(target))

    @app.post("/api/v1/engineering/reviews/{review_type}", tags=["engineering"])
    async def engineering_review(review_type: str, body: dict[str, Any] = Body({})) -> dict[str, Any]:
        """Run a single review of the given type."""
        target = body.get("target", ".")
        mgr = _get_engineering_manager()
        return cast("dict[str, Any]", await mgr.review(review_type, target))

    @app.get("/api/v1/engineering/reviews/types", tags=["engineering"])
    async def engineering_review_types() -> dict[str, Any]:
        """List the 12 supported review types."""
        from services.engineering import ReviewType
        return {"review_types": [rt.value for rt in ReviewType]}

    # --- Test Intelligence (Phase 18) ---

    @app.get("/api/v1/engineering/test-intelligence/analysis", tags=["engineering"])
    async def test_intelligence_analysis() -> dict[str, Any]:
        """Analyze the test suite."""
        mgr = _get_engineering_manager()
        return cast("dict[str, Any]", await mgr.test_suite_analysis())

    @app.get("/api/v1/engineering/test-intelligence/coverage", tags=["engineering"])
    async def test_intelligence_coverage() -> dict[str, Any]:
        """Generate a test coverage report."""
        mgr = _get_engineering_manager()
        return cast("dict[str, Any]", await mgr.test_coverage())

    @app.post("/api/v1/engineering/test-intelligence/risk", tags=["engineering"])
    async def test_intelligence_risk(body: dict[str, Any] = Body({})) -> dict[str, Any]:
        """Generate a test risk report."""
        mgr = _get_engineering_manager()
        recent_failures = body.get("recent_failures")
        return cast("dict[str, Any]", await mgr.test_risk(recent_failures=recent_failures))

    # --- Documentation Intelligence (Phase 19) ---

    @app.get("/api/v1/engineering/documentation/analysis", tags=["engineering"])
    async def documentation_analysis() -> dict[str, Any]:
        """Analyze the documentation."""
        mgr = _get_engineering_manager()
        return cast("dict[str, Any]", await mgr.documentation_analysis())

    @app.get("/api/v1/engineering/documentation/recommendations", tags=["engineering"])
    async def documentation_recommendations() -> dict[str, Any]:
        """Get documentation recommendations."""
        mgr = _get_engineering_manager()
        recs = cast("list[dict[str, Any]]", await mgr.documentation_recommendations())
        return {"recommendations": recs, "count": len(recs)}

    # --- Repository Evolution (Phase 20) ---

    @app.get("/api/v1/engineering/repository/evolution", tags=["engineering"])
    async def repository_evolution() -> dict[str, Any]:
        """Get the repository evolution dashboard."""
        mgr = _get_engineering_manager()
        return cast("dict[str, Any]", await mgr.evolution_dashboard())

    @app.get("/api/v1/engineering/repository/timeline", tags=["engineering"])
    async def repository_timeline(limit: int = 50) -> dict[str, Any]:
        """Get the repository timeline."""
        mgr = _get_engineering_manager()
        entries = cast("list[dict[str, Any]]", await mgr.evolution_timeline(limit=limit))
        return {"entries": entries, "count": len(entries)}

    @app.get("/api/v1/engineering/repository/analysis", tags=["engineering"])
    async def repository_analysis_v2() -> dict[str, Any]:
        """Analyze the repository structure."""
        mgr = _get_engineering_manager()
        return cast("dict[str, Any]", await mgr.analyze_repository())

    # --- Release Readiness (Phase 21) ---

    @app.post("/api/v1/engineering/release/readiness", tags=["engineering"])
    async def release_readiness(body: dict[str, Any] = Body({})) -> dict[str, Any]:
        """Evaluate release readiness."""
        version = body.get("version", "")
        mgr = _get_engineering_manager()
        return cast("dict[str, Any]", await mgr.release_readiness(version=version))

    @app.post("/api/v1/engineering/release/certification", tags=["engineering"])
    async def release_certification(body: dict[str, Any] = Body({})) -> dict[str, Any]:
        """Generate a certification report."""
        version = body.get("version", "")
        mgr = _get_engineering_manager()
        return cast("dict[str, Any]", await mgr.certification_report(version=version))

    # --- Developer Productivity (Phase 22) ---

    @app.get("/api/v1/engineering/productivity/dashboard", tags=["engineering"])
    async def productivity_dashboard() -> dict[str, Any]:
        """Get the developer productivity dashboard."""
        mgr = _get_engineering_manager()
        return cast("dict[str, Any]", await mgr.productivity_dashboard())

    @app.get("/api/v1/engineering/productivity/metrics", tags=["engineering"])
    async def productivity_metrics() -> dict[str, Any]:
        """Get current productivity metrics."""
        mgr = _get_engineering_manager()
        return cast("dict[str, Any]", await mgr.productivity_metrics())

    @app.get("/api/v1/engineering/productivity/dora", tags=["engineering"])
    async def productivity_dora() -> dict[str, Any]:
        """Get DORA metrics."""
        mgr = _get_engineering_manager()
        return cast("dict[str, Any]", await mgr.productivity_dora())

    @app.post("/api/v1/engineering/productivity/events", tags=["engineering"])
    async def productivity_record_event(body: dict[str, Any] = Body(...)) -> dict[str, str]:
        """Record a productivity event."""
        mgr = _get_engineering_manager()
        mgr.record_productivity_event(body)
        return {"status": "recorded"}

    @app.get("/api/v1/engineering/productivity/report", tags=["engineering"])
    async def productivity_report() -> dict[str, Any]:
        """Get the full productivity report."""
        mgr = _get_engineering_manager()
        return cast("dict[str, Any]", await mgr.productivity_report())

    # --- Repository Health Center (Phase 23) ---

    @app.get("/api/v1/engineering/health", tags=["engineering"])
    async def engineering_health() -> dict[str, Any]:
        """Get the repository health report."""
        mgr = _get_engineering_manager()
        return cast("dict[str, Any]", await mgr.health())

    @app.get("/api/v1/engineering/health/score", tags=["engineering"])
    async def engineering_health_score() -> dict[str, float]:
        """Get the overall repository health score (0..100)."""
        mgr = _get_engineering_manager()
        score = await mgr.health_quick_score()
        return {"score": round(score, 2)}

    # --- Planning (Phase 25 CLI / API) ---

    @app.post("/api/v1/engineering/planning/create", tags=["engineering"])
    async def planning_create(body: dict[str, Any] = Body({})) -> dict[str, Any]:
        """Create an engineering plan."""
        from services.engineering import PlanningEngine
        title = body.get("title", "")
        description = body.get("description", "")
        requirements = body.get("requirements", [])
        engine = PlanningEngine()
        plan = await engine.create_plan(
            title=title, description=description, requirements=requirements,
        )
        return plan.to_dict()

    @app.post("/api/v1/engineering/planning/impact", tags=["engineering"])
    async def planning_impact(body: dict[str, Any] = Body(...)) -> dict[str, Any]:
        """Analyze the impact of a change to ``target``."""
        from pathlib import Path
        target = body.get("target", "")
        change_description = body.get("change_description", "")
        engine = _get_impact_analysis()
        result = await engine.analyze_impact(Path(), target, change_description)
        return cast("dict[str, Any]", result.to_dict())

    # ------------------------------------------------------------------
    # v5.3 — Research & Reasoning Platform API
    # ------------------------------------------------------------------

    _research_manager: Any = None

    def _get_research_manager() -> Any:
        nonlocal _research_manager
        if _research_manager is None:
            from services.research import ResearchManager
            _research_manager = ResearchManager()
        return _research_manager

    @app.get("/api/v1/research/overview", tags=["research"])
    async def research_overview() -> dict[str, Any]:
        """Research platform overview."""
        mgr = _get_research_manager()
        return cast("dict[str, Any]", await mgr.get_overview())

    @app.get("/api/v1/research/projects", tags=["research"])
    async def research_projects(
        status: str | None = None, domain: str | None = None,
    ) -> dict[str, Any]:
        """List research projects."""
        mgr = _get_research_manager()
        projects = await mgr.list_projects(status=status, domain=domain)
        return {"projects": [p.to_dict() for p in projects], "count": len(projects)}

    @app.post("/api/v1/research/projects", tags=["research"])
    async def research_create_project(body: dict[str, Any] = Body(...)) -> dict[str, Any]:
        """Create a research project."""
        mgr = _get_research_manager()
        project = await mgr.create_project(
            body.get("title", ""),
            body.get("description", ""),
            domain=body.get("domain", ""),
            owner=body.get("owner", ""),
        )
        return cast("dict[str, Any]", project.to_dict())

    @app.get("/api/v1/research/projects/{project_id}", tags=["research"])
    async def research_get_project(project_id: str) -> dict[str, Any]:
        """Get a research project."""
        mgr = _get_research_manager()
        project = await mgr.get_project(project_id)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        return cast("dict[str, Any]", project.to_dict())

    @app.get("/api/v1/research/agents", tags=["research"])
    async def research_agents() -> dict[str, Any]:
        """List the 10 specialized research agents."""
        mgr = _get_research_manager()
        return {"agents": mgr.list_research_agents(), "count": 10}

    @app.post("/api/v1/research/agents/{agent_type}/research", tags=["research"])
    async def research_agent_run(
        agent_type: str, body: dict[str, Any] = Body(...),
    ) -> dict[str, Any]:
        """Run research with a specific agent."""
        mgr = _get_research_manager()
        query = body.get("query", "")
        source_material = body.get("source_material")
        finding = await mgr.research_with_agent(
            agent_type, query, source_material=source_material,
        )
        if not finding:
            raise HTTPException(status_code=404, detail=f"Unknown agent type: {agent_type}")
        return cast("dict[str, Any]", finding.to_dict())

    @app.post("/api/v1/research/reasoning", tags=["research"])
    async def research_reasoning(body: dict[str, Any] = Body(...)) -> dict[str, Any]:
        """Run multi-model reasoning.

        Accepts a ``question`` and an optional list of pre-computed ``analyses``
        (each with model, provider, claims, confidence, response). If no
        analyses are provided, returns a low-confidence placeholder.
        """
        mgr = _get_research_manager()
        from services.research import ModelAnalysis
        question = body.get("question", "")
        raw_analyses = body.get("analyses", []) or []
        analyses: list[ModelAnalysis] = []
        for a in raw_analyses:
            analyses.append(ModelAnalysis(
                model=a.get("model", ""),
                provider=a.get("provider", ""),
                response=a.get("response", ""),
                reasoning=a.get("reasoning", ""),
                claims=a.get("claims", []),
                confidence=float(a.get("confidence", 0.5)),
            ))
        result = await mgr.reason(question, analyses)
        return cast("dict[str, Any]", result.to_dict())

    @app.get("/api/v1/research/evidence-graph", tags=["research"])
    async def research_evidence_graph() -> dict[str, Any]:
        """Evidence graph statistics."""
        mgr = _get_research_manager()
        return cast("dict[str, Any]", mgr.evidence_graph_stats())

    @app.get("/api/v1/research/evidence-graph/search", tags=["research"])
    async def research_evidence_graph_search(
        q: str = "", kinds: str | None = None,
    ) -> dict[str, Any]:
        """Search the evidence graph."""
        mgr = _get_research_manager()
        kind_list = kinds.split(",") if kinds else None
        nodes = mgr.evidence_graph_search(q, kinds=kind_list)
        return {"nodes": nodes, "count": len(nodes)}

    @app.post("/api/v1/research/verification", tags=["research"])
    async def research_verification(body: dict[str, Any] = Body(...)) -> dict[str, Any]:
        """Verify a fact against a list of sources."""
        mgr = _get_research_manager()
        from services.research import Source
        fact_text = body.get("fact_text", "")
        raw_sources = body.get("sources", []) or []
        sources: list[Source] = []
        for s in raw_sources:
            sources.append(Source(
                title=s.get("title", ""),
                url=s.get("url", ""),
                abstract=s.get("abstract", ""),
                reliability=s.get("reliability", "tier_3_established"),
                reliability_score=float(s.get("reliability_score", 0.5)),
                source_type=s.get("source_type", ""),
                authors=s.get("authors", []),
            ))
        report = await mgr.verify_fact(fact_text, sources)
        return cast("dict[str, Any]", report.to_dict())

    @app.post("/api/v1/research/synthesis", tags=["research"])
    async def research_synthesis(body: dict[str, Any] = Body(...)) -> dict[str, Any]:
        """Synthesize knowledge from multiple documents."""
        mgr = _get_research_manager()
        from datetime import datetime

        from services.research import Source
        project_id = body.get("project_id", "")
        title = body.get("title", "Synthesis")
        description = body.get("description", "")
        research_question = body.get("research_question", "")
        raw_docs = body.get("documents", []) or []
        documents: list[Source] = []
        for d in raw_docs:
            published_at_str = d.get("published_at")
            published_at = None
            if published_at_str:
                try:
                    published_at = datetime.fromisoformat(published_at_str)
                except (ValueError, TypeError):
                    published_at = None
            documents.append(Source(
                title=d.get("title", ""),
                url=d.get("url", ""),
                abstract=d.get("abstract", ""),
                reliability=d.get("reliability", "tier_3_established"),
                reliability_score=float(d.get("reliability_score", 0.5)),
                source_type=d.get("source_type", ""),
                authors=d.get("authors", []),
                published_at=published_at,
            ))
        synthesis = await mgr.synthesize(
            project_id, title, documents,
            description=description, research_question=research_question,
        )
        return cast("dict[str, Any]", synthesis.to_dict())

    @app.get("/api/v1/research/timeline", tags=["research"])
    async def research_timeline(
        project_id: str | None = None, limit: int = 50,
    ) -> dict[str, Any]:
        """Research timeline."""
        mgr = _get_research_manager()
        entries = await mgr.timeline(project_id=project_id, limit=limit)
        return {"entries": entries, "count": len(entries)}

    @app.get("/api/v1/research/stats", tags=["research"])
    async def research_stats() -> dict[str, Any]:
        """Research engine statistics."""
        mgr = _get_research_manager()
        return cast("dict[str, Any]", await mgr.stats())

    # ------------------------------------------------------------------
    # v5.3.2 — Installer API
    # ------------------------------------------------------------------

    _installer: Any = None

    def _get_installer() -> Any:
        nonlocal _installer
        if _installer is None:
            from services.installer import InstallerOrchestrator
            _installer = InstallerOrchestrator()
        return _installer

    @app.post("/api/v1/installer/environment", tags=["installer"])
    async def installer_environment() -> dict[str, Any]:
        """Detect the host environment."""
        from services.installer import EnvironmentDetector
        detector = EnvironmentDetector()
        report = detector.detect()
        compat = detector.assess_compatibility(report)
        return {
            "environment": report.to_dict(),
            "compatibility": compat.to_dict(),
        }

    @app.post("/api/v1/installer/install", tags=["installer"])
    async def installer_install(body: dict[str, Any] = Body({})) -> dict[str, Any]:
        """Run the installer in the given mode."""
        mode = body.get("mode", "interactive")
        workspace = body.get("workspace_root", "")
        profile = body.get("profile", "")
        force = bool(body.get("force", False))
        orchestrator = _get_installer()
        report = await orchestrator.install(
            mode=mode, workspace_root=workspace,
            profile=profile if profile else None,
            force=force,
        )
        return cast("dict[str, Any]", report.to_dict())

    @app.post("/api/v1/installer/validate", tags=["installer"])
    async def installer_validate() -> dict[str, Any]:
        """Validate an existing installation."""
        orchestrator = _get_installer()
        report = await orchestrator.validate()
        return cast("dict[str, Any]", report.to_dict())

    @app.post("/api/v1/installer/repair", tags=["installer"])
    async def installer_repair() -> dict[str, Any]:
        """Repair an existing installation."""
        orchestrator = _get_installer()
        report = await orchestrator.repair()
        return cast("dict[str, Any]", report.to_dict())

    @app.get("/api/v1/installer/dependencies", tags=["installer"])
    async def installer_dependencies() -> dict[str, Any]:
        """List all known dependencies and their status."""
        from services.installer import DependencyChecker
        checker = DependencyChecker()
        checks = checker.check_all()
        return {
            "dependencies": [c.to_dict() for c in checks],
            "count": len(checks),
        }

    @app.get("/api/v1/installer/providers", tags=["installer"])
    async def installer_providers() -> dict[str, Any]:
        """List all supported LLM providers."""
        from services.installer import ProviderConfigurator
        configurator = ProviderConfigurator()
        return {"providers": configurator.list_supported()}

    @app.get("/api/v1/installer/agents", tags=["installer"])
    async def installer_agents() -> dict[str, Any]:
        """List all supported agents."""
        from services.installer import AgentBootstrapper
        bootstrapper = AgentBootstrapper()
        results = bootstrapper.discover_all()
        return {
            "agents": [r.to_dict() for r in results],
            "count": len(results),
        }

    return app
