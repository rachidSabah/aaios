"""Phase 1 — Enterprise Research Engine.

Manages research projects, sessions, plans, tasks, pipelines, history,
templates, memory, workspaces, and timelines. All operations are
auditable. No automatic publication — every exported artifact requires
human approval.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from core.logging import get_logger
from services.research.models import (
    ResearchFinding,
    ResearchMemory,
    ResearchPipeline,
    ResearchPipelineStage,
    ResearchPlan,
    ResearchProject,
    ResearchSession,
    ResearchTask,
    ResearchTemplate,
    ResearchTimelineEntry,
    ResearchWorkspace,
)

_log = get_logger(__name__)

__all__ = [
    "ResearchEngine",
    "ResearchHistory",
]


@dataclass
class ResearchHistory:
    """A read-only view of past research activity."""

    project_id: str = ""
    sessions: list[ResearchSession] = field(default_factory=list)
    findings: list[ResearchFinding] = field(default_factory=list)
    timeline: list[ResearchTimelineEntry] = field(default_factory=list)
    memory_entries: list[ResearchMemory] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "project_id": self.project_id,
            "sessions": [s.to_dict() for s in self.sessions],
            "findings": [f.to_dict() for f in self.findings],
            "timeline": [t.to_dict() for t in self.timeline],
            "memory_entries": [m.to_dict() for m in self.memory_entries],
        }


class ResearchEngine:
    """Phase 1 — Enterprise Research Engine.

    In-memory store for research projects, sessions, plans, tasks,
    pipelines, templates, memory, workspaces, and timelines. Designed
    for extension — a persistent backend can be added without changing
    the public API.
    """

    def __init__(self) -> None:
        self._projects: dict[str, ResearchProject] = {}
        self._sessions: dict[str, ResearchSession] = {}
        self._plans: dict[str, ResearchPlan] = {}
        self._tasks: dict[str, ResearchTask] = {}
        self._pipelines: dict[str, ResearchPipeline] = {}
        self._templates: dict[str, ResearchTemplate] = {}
        self._memory: dict[str, ResearchMemory] = {}
        self._workspaces: dict[str, ResearchWorkspace] = {}
        self._timeline: list[ResearchTimelineEntry] = []
        self._findings: dict[str, ResearchFinding] = {}

    # --- Projects -------------------------------------------------------

    async def create_project(
        self,
        title: str,
        description: str = "",
        *,
        domain: str = "",
        owner: str = "",
        objectives: list[str] | None = None,
        research_questions: list[str] | None = None,
        collaborators: list[str] | None = None,
        tags: list[str] | None = None,
    ) -> ResearchProject:
        project = ResearchProject(
            title=title,
            description=description,
            domain=domain,
            owner=owner,
            objectives=objectives or [],
            research_questions=research_questions or [],
            collaborators=collaborators or [],
            tags=tags or [],
        )
        self._projects[project.project_id] = project
        self._add_timeline(project.project_id, "project_created", f"Project '{title}' created", actor=owner)
        _log.info("research.project_created", project_id=project.project_id, title=title)
        return project

    async def get_project(self, project_id: str) -> ResearchProject | None:
        return self._projects.get(project_id)

    async def list_projects(
        self, *, status: str | None = None, domain: str | None = None
    ) -> list[ResearchProject]:
        out = list(self._projects.values())
        if status:
            out = [p for p in out if p.status == status]
        if domain:
            out = [p for p in out if p.domain == domain]
        return out

    async def update_project(
        self, project_id: str, **updates: Any
    ) -> ResearchProject | None:
        project = self._projects.get(project_id)
        if not project:
            return None
        for key, value in updates.items():
            if hasattr(project, key) and key != "project_id":
                setattr(project, key, value)
        project.updated_at = datetime.now(UTC)
        self._add_timeline(project_id, "project_updated", f"Project updated: {list(updates.keys())}")
        return project

    async def start_project(self, project_id: str) -> ResearchProject | None:
        project = self._projects.get(project_id)
        if not project:
            return None
        project.status = "active"
        project.started_at = datetime.now(UTC)
        project.updated_at = datetime.now(UTC)
        self._add_timeline(project_id, "project_started", "Project started")
        return project

    async def complete_project(self, project_id: str) -> ResearchProject | None:
        project = self._projects.get(project_id)
        if not project:
            return None
        project.status = "completed"
        project.completed_at = datetime.now(UTC)
        project.updated_at = datetime.now(UTC)
        self._add_timeline(project_id, "project_completed", "Project completed")
        return project

    async def delete_project(self, project_id: str) -> bool:
        if project_id not in self._projects:
            return False
        del self._projects[project_id]
        # Cascade-delete related sessions, plans, findings
        for sid in [s.session_id for s in self._sessions.values() if s.project_id == project_id]:
            del self._sessions[sid]
        for pid in [p.plan_id for p in self._plans.values() if p.project_id == project_id]:
            del self._plans[pid]
        for fid in [f.finding_id for f in self._findings.values() if f.project_id == project_id]:
            del self._findings[fid]
        self._add_timeline(project_id, "project_deleted", "Project deleted")
        return True

    # --- Sessions -------------------------------------------------------

    async def create_session(
        self,
        project_id: str,
        title: str,
        query: str,
        *,
        scope: str = "focused",
        agent_type: str = "",
    ) -> ResearchSession | None:
        if project_id not in self._projects:
            return None
        session = ResearchSession(
            project_id=project_id,
            title=title,
            query=query,
            scope=scope,
            agent_type=agent_type,
        )
        self._sessions[session.session_id] = session
        project = self._projects[project_id]
        project.session_count += 1
        self._add_timeline(project_id, "session_created", f"Session '{title}' created", session_id=session.session_id)
        return session

    async def get_session(self, session_id: str) -> ResearchSession | None:
        return self._sessions.get(session_id)

    async def list_sessions(
        self, *, project_id: str | None = None, status: str | None = None
    ) -> list[ResearchSession]:
        out = list(self._sessions.values())
        if project_id:
            out = [s for s in out if s.project_id == project_id]
        if status:
            out = [s for s in out if s.status == status]
        return out

    async def start_session(self, session_id: str) -> ResearchSession | None:
        session = self._sessions.get(session_id)
        if not session:
            return None
        session.status = "running"
        session.started_at = datetime.now(UTC)
        self._add_timeline(session.project_id, "session_started", f"Session '{session.title}' started", session_id)
        return session

    async def complete_session(
        self,
        session_id: str,
        *,
        finding_count: int = 0,
        sources_consulted: int = 0,
        models_used: list[str] | None = None,
        error: str | None = None,
    ) -> ResearchSession | None:
        session = self._sessions.get(session_id)
        if not session:
            return None
        session.status = "failed" if error else "completed"
        session.completed_at = datetime.now(UTC)
        if session.started_at:
            session.duration_s = (session.completed_at - session.started_at).total_seconds()
        session.finding_count = finding_count
        session.sources_consulted = sources_consulted
        session.models_used = models_used or []
        session.error = error
        kind = "session_failed" if error else "session_completed"
        self._add_timeline(session.project_id, kind, f"Session '{session.title}' {kind}", session_id)
        return session

    # --- Plans ----------------------------------------------------------

    async def create_plan(
        self,
        project_id: str,
        title: str,
        description: str = "",
        *,
        objectives: list[str] | None = None,
        research_questions: list[str] | None = None,
        methodology: str = "",
        agent_assignments: dict[str, list[str]] | None = None,
        expected_outputs: list[str] | None = None,
    ) -> ResearchPlan | None:
        if project_id not in self._projects:
            return None
        plan = ResearchPlan(
            project_id=project_id,
            title=title,
            description=description,
            objectives=objectives or [],
            research_questions=research_questions or [],
            methodology=methodology,
            agent_assignments=agent_assignments or {},
            expected_outputs=expected_outputs or [],
        )
        self._plans[plan.plan_id] = plan
        self._add_timeline(project_id, "plan_created", f"Plan '{title}' created")
        return plan

    async def get_plan(self, plan_id: str) -> ResearchPlan | None:
        return self._plans.get(plan_id)

    async def list_plans(self, *, project_id: str | None = None) -> list[ResearchPlan]:
        out = list(self._plans.values())
        if project_id:
            out = [p for p in out if p.project_id == project_id]
        return out

    # --- Tasks ----------------------------------------------------------

    async def create_task(
        self,
        session_id: str,
        title: str,
        description: str = "",
        *,
        agent_type: str = "",
        priority: str = "normal",
        dependencies: list[str] | None = None,
        estimated_minutes: float = 0.0,
        inputs: dict[str, Any] | None = None,
    ) -> ResearchTask | None:
        if session_id not in self._sessions:
            return None
        task = ResearchTask(
            session_id=session_id,
            title=title,
            description=description,
            agent_type=agent_type,
            priority=priority,
            dependencies=dependencies or [],
            estimated_minutes=estimated_minutes,
            inputs=inputs or {},
        )
        self._tasks[task.task_id] = task
        session = self._sessions[session_id]
        self._add_timeline(session.project_id, "task_created", f"Task '{title}' created", session_id)
        return task

    async def get_task(self, task_id: str) -> ResearchTask | None:
        return self._tasks.get(task_id)

    async def list_tasks(
        self, *, session_id: str | None = None, status: str | None = None
    ) -> list[ResearchTask]:
        out = list(self._tasks.values())
        if session_id:
            out = [t for t in out if t.session_id == session_id]
        if status:
            out = [t for t in out if t.status == status]
        return out

    async def complete_task(
        self,
        task_id: str,
        *,
        outputs: dict[str, Any] | None = None,
        actual_minutes: float = 0.0,
        error: str | None = None,
    ) -> ResearchTask | None:
        task = self._tasks.get(task_id)
        if not task:
            return None
        task.status = "failed" if error else "completed"
        task.outputs = outputs or {}
        task.actual_minutes = actual_minutes
        task.error = error
        task.completed_at = datetime.now(UTC)
        return task

    # --- Pipelines ------------------------------------------------------

    async def create_pipeline(
        self,
        project_id: str,
        name: str,
        description: str = "",
        *,
        stages: list[ResearchPipelineStage] | None = None,
    ) -> ResearchPipeline | None:
        if project_id not in self._projects:
            return None
        pipeline = ResearchPipeline(
            project_id=project_id,
            name=name,
            description=description,
            stages=stages or [],
        )
        self._pipelines[pipeline.pipeline_id] = pipeline
        self._add_timeline(project_id, "pipeline_created", f"Pipeline '{name}' created")
        return pipeline

    async def get_pipeline(self, pipeline_id: str) -> ResearchPipeline | None:
        return self._pipelines.get(pipeline_id)

    async def list_pipelines(self, *, project_id: str | None = None) -> list[ResearchPipeline]:
        out = list(self._pipelines.values())
        if project_id:
            out = [p for p in out if p.project_id == project_id]
        return out

    async def execute_pipeline(self, pipeline_id: str) -> ResearchPipeline | None:
        """Mark all pipeline stages as completed (synchronous stub).

        Real execution would dispatch each stage to its assigned agent.
        """
        pipeline = self._pipelines.get(pipeline_id)
        if not pipeline:
            return None
        pipeline.status = "running"
        pipeline.started_at = datetime.now(UTC)
        for stage in pipeline.stages:
            stage.status = "completed"
        pipeline.status = "completed"
        pipeline.completed_at = datetime.now(UTC)
        self._add_timeline(pipeline.project_id, "pipeline_completed", f"Pipeline '{pipeline.name}' executed")
        return pipeline

    # --- Templates ------------------------------------------------------

    async def create_template(
        self,
        name: str,
        description: str = "",
        *,
        domain: str = "",
        objectives: list[str] | None = None,
        research_questions: list[str] | None = None,
        methodology: str = "",
        recommended_agents: list[str] | None = None,
        expected_duration_hours: float = 0.0,
        tags: list[str] | None = None,
    ) -> ResearchTemplate:
        template = ResearchTemplate(
            name=name,
            description=description,
            domain=domain,
            objectives=objectives or [],
            research_questions=research_questions or [],
            methodology=methodology,
            recommended_agents=recommended_agents or [],
            expected_duration_hours=expected_duration_hours,
            tags=tags or [],
        )
        self._templates[template.template_id] = template
        return template

    async def get_template(self, template_id: str) -> ResearchTemplate | None:
        return self._templates.get(template_id)

    async def list_templates(
        self, *, domain: str | None = None
    ) -> list[ResearchTemplate]:
        out = list(self._templates.values())
        if domain:
            out = [t for t in out if t.domain == domain]
        return out

    async def instantiate_template(
        self, template_id: str, title: str, owner: str = ""
    ) -> ResearchProject | None:
        """Create a new project from a template."""
        template = self._templates.get(template_id)
        if not template:
            return None
        return await self.create_project(
            title=title,
            description=template.description,
            domain=template.domain,
            owner=owner,
            objectives=list(template.objectives),
            research_questions=list(template.research_questions),
            tags=list(template.tags),
        )

    # --- Memory ---------------------------------------------------------

    async def add_memory(
        self,
        project_id: str,
        memory_type: str,
        key: str,
        value: str,
        *,
        evidence: list[str] | None = None,
        confidence: float = 0.5,
        relevance_score: float = 0.5,
    ) -> ResearchMemory:
        memory = ResearchMemory(
            project_id=project_id,
            memory_type=memory_type,
            key=key,
            value=value,
            evidence=evidence or [],
            confidence=confidence,
            relevance_score=relevance_score,
        )
        self._memory[memory.memory_id] = memory
        return memory

    async def get_memory(self, memory_id: str) -> ResearchMemory | None:
        mem = self._memory.get(memory_id)
        if mem:
            mem.last_accessed_at = datetime.now(UTC)
            mem.access_count += 1
        return mem

    async def list_memory(
        self,
        *,
        project_id: str | None = None,
        memory_type: str | None = None,
    ) -> list[ResearchMemory]:
        out = list(self._memory.values())
        if project_id:
            out = [m for m in out if m.project_id == project_id]
        if memory_type:
            out = [m for m in out if m.memory_type == memory_type]
        return out

    async def search_memory(self, query: str) -> list[ResearchMemory]:
        """Simple substring search across memory keys and values."""
        q = query.lower()
        return [
            m for m in self._memory.values()
            if q in m.key.lower() or q in m.value.lower()
        ]

    # --- Workspaces -----------------------------------------------------

    async def create_workspace(
        self,
        name: str,
        description: str = "",
        *,
        owner: str = "",
        collaborators: list[str] | None = None,
        project_ids: list[str] | None = None,
    ) -> ResearchWorkspace:
        ws = ResearchWorkspace(
            name=name,
            description=description,
            owner=owner,
            collaborators=collaborators or [],
            project_ids=project_ids or [],
        )
        self._workspaces[ws.workspace_id] = ws
        return ws

    async def get_workspace(self, workspace_id: str) -> ResearchWorkspace | None:
        return self._workspaces.get(workspace_id)

    async def list_workspaces(self) -> list[ResearchWorkspace]:
        return list(self._workspaces.values())

    async def add_project_to_workspace(
        self, workspace_id: str, project_id: str
    ) -> ResearchWorkspace | None:
        ws = self._workspaces.get(workspace_id)
        if not ws:
            return None
        if project_id not in ws.project_ids:
            ws.project_ids.append(project_id)
        return ws

    # --- Timeline -------------------------------------------------------

    async def timeline(
        self,
        *,
        project_id: str | None = None,
        session_id: str | None = None,
        kind: str | None = None,
        limit: int = 100,
    ) -> list[ResearchTimelineEntry]:
        out = list(self._timeline)
        if project_id:
            out = [e for e in out if e.project_id == project_id]
        if session_id:
            out = [e for e in out if e.session_id == session_id]
        if kind:
            out = [e for e in out if e.kind == kind]
        out.sort(key=lambda e: e.timestamp, reverse=True)
        return out[:limit]

    def _add_timeline(
        self,
        project_id: str,
        kind: str,
        description: str,
        session_id: str = "",
        actor: str = "",
    ) -> None:
        entry = ResearchTimelineEntry(
            project_id=project_id,
            session_id=session_id,
            kind=kind,
            title=kind.replace("_", " ").title(),
            description=description,
            actor=actor or "research-engine",
        )
        self._timeline.append(entry)

    # --- Findings -------------------------------------------------------

    async def add_finding(
        self,
        project_id: str,
        session_id: str,
        title: str,
        description: str = "",
        *,
        claims: list[str] | None = None,
        confidence: float = 0.5,
        evidence: list[str] | None = None,
        tags: list[str] | None = None,
    ) -> ResearchFinding | None:
        if project_id not in self._projects:
            return None
        finding = ResearchFinding(
            project_id=project_id,
            session_id=session_id,
            title=title,
            description=description,
            claims=claims or [],
            confidence=confidence,
            evidence=evidence or [],
            tags=tags or [],
        )
        self._findings[finding.finding_id] = finding
        project = self._projects[project_id]
        project.finding_count += 1
        self._add_timeline(project_id, "finding_added", f"Finding '{title}' added", session_id)
        return finding

    async def get_finding(self, finding_id: str) -> ResearchFinding | None:
        return self._findings.get(finding_id)

    async def list_findings(
        self,
        *,
        project_id: str | None = None,
        session_id: str | None = None,
    ) -> list[ResearchFinding]:
        out = list(self._findings.values())
        if project_id:
            out = [f for f in out if f.project_id == project_id]
        if session_id:
            out = [f for f in out if f.session_id == session_id]
        return out

    # --- History --------------------------------------------------------

    async def history(self, project_id: str) -> ResearchHistory:
        """Get a complete read-only view of a project's research activity."""
        return ResearchHistory(
            project_id=project_id,
            sessions=[s for s in self._sessions.values() if s.project_id == project_id],
            findings=[f for f in self._findings.values() if f.project_id == project_id],
            timeline=[t for t in self._timeline if t.project_id == project_id],
            memory_entries=[m for m in self._memory.values() if m.project_id == project_id],
        )

    # --- Statistics -----------------------------------------------------

    async def stats(self) -> dict[str, Any]:
        """Aggregate research engine statistics."""
        projects_by_status: dict[str, int] = defaultdict(int)
        for p in self._projects.values():
            projects_by_status[p.status] += 1
        sessions_by_status: dict[str, int] = defaultdict(int)
        for s in self._sessions.values():
            sessions_by_status[s.status] += 1
        return {
            "projects": len(self._projects),
            "sessions": len(self._sessions),
            "plans": len(self._plans),
            "tasks": len(self._tasks),
            "pipelines": len(self._pipelines),
            "templates": len(self._templates),
            "memory_entries": len(self._memory),
            "workspaces": len(self._workspaces),
            "findings": len(self._findings),
            "timeline_entries": len(self._timeline),
            "projects_by_status": dict(projects_by_status),
            "sessions_by_status": dict(sessions_by_status),
        }
