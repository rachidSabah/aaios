"""Workflow Store — persistent DAG definitions for the visual workflow builder.

A workflow is a directed acyclic graph of steps (nodes) connected by edges.
Each node references a capability (e.g. `code.generate`, `desktop.screenshot`)
plus parameters. The workflow store supports CRUD, validation (DAG check),
and JSON persistence.

This is the backend that powers the dashboard's visual workflow builder.
The frontend renders nodes as boxes and edges as arrows; this module is
the source of truth.
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from core.logging import get_logger

_log = get_logger(__name__)

__all__ = [
    "Workflow",
    "WorkflowEdge",
    "WorkflowNode",
    "WorkflowNotFoundError",
    "WorkflowStore",
    "WorkflowValidationError",
]


class WorkflowValidationError(Exception):
    """Raised when a workflow definition is invalid (cycle, missing node, etc.)."""


class WorkflowNotFoundError(Exception):
    """Raised when a workflow ID is not found in the store."""


@dataclass
class WorkflowNode:
    """A single step in a workflow.

    Each node has:
      - id: unique within the workflow (short string, e.g. "n1")
      - capability: the capability namespace this node invokes
        (e.g. "code.generate", "desktop.screenshot", "memory.recall")
      - label: human-readable name shown in the UI
      - parameters: arbitrary JSON-serializable parameters passed to the agent
      - position: optional {x, y} coordinates for UI placement
    """

    id: str
    capability: str
    label: str
    parameters: dict[str, Any] = field(default_factory=dict)
    position: dict[str, float] | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> WorkflowNode:
        return cls(
            id=str(data["id"]),
            capability=str(data["capability"]),
            label=str(data["label"]),
            parameters=dict(data.get("parameters", {})),
            position=dict(data["position"]) if data.get("position") else None,
        )


@dataclass
class WorkflowEdge:
    """A directed edge between two nodes — `source` -> `target`."""

    source: str
    target: str
    label: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> WorkflowEdge:
        return cls(
            source=str(data["source"]),
            target=str(data["target"]),
            label=str(data.get("label", "")),
        )


@dataclass
class Workflow:
    """A complete workflow definition (DAG of nodes + edges)."""

    id: str
    name: str
    description: str = ""
    nodes: list[WorkflowNode] = field(default_factory=list)
    edges: list[WorkflowEdge] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "nodes": [n.to_dict() for n in self.nodes],
            "edges": [e.to_dict() for e in self.edges],
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "tags": list(self.tags),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Workflow:
        return cls(
            id=str(data["id"]),
            name=str(data["name"]),
            description=str(data.get("description", "")),
            nodes=[WorkflowNode.from_dict(n) for n in data.get("nodes", [])],
            edges=[WorkflowEdge.from_dict(e) for e in data.get("edges", [])],
            tags=list(data.get("tags", [])),
        )

    def validate(self) -> None:
        """Validate the workflow — check node IDs unique, edges reference
        existing nodes, and the graph is acyclic.

        Raises WorkflowValidationError on any issue.
        """
        node_ids = [n.id for n in self.nodes]
        if len(node_ids) != len(set(node_ids)):
            raise WorkflowValidationError("Duplicate node IDs in workflow")
        node_id_set = set(node_ids)
        for edge in self.edges:
            if edge.source not in node_id_set:
                raise WorkflowValidationError(
                    f"Edge source '{edge.source}' not in nodes",
                )
            if edge.target not in node_id_set:
                raise WorkflowValidationError(
                    f"Edge target '{edge.target}' not in nodes",
                )
        # Cycle detection via DFS
        adjacency: dict[str, list[str]] = {nid: [] for nid in node_ids}
        for edge in self.edges:
            adjacency[edge.source].append(edge.target)

        WHITE, GRAY, BLACK = 0, 1, 2
        color: dict[str, int] = dict.fromkeys(node_ids, WHITE)

        def dfs(node: str) -> bool:
            color[node] = GRAY
            for neighbor in adjacency[node]:
                if color[neighbor] == GRAY:
                    return True  # back edge → cycle
                if color[neighbor] == WHITE and dfs(neighbor):
                    return True
            color[node] = BLACK
            return False

        for nid in node_ids:
            if color[nid] == WHITE and dfs(nid):
                raise WorkflowValidationError(
                    f"Workflow '{self.name}' contains a cycle",
                )

    def topological_order(self) -> list[str]:
        """Return node IDs in topological order (sources first)."""
        self.validate()  # raises on cycle
        adjacency: dict[str, list[str]] = {n.id: [] for n in self.nodes}
        in_degree: dict[str, int] = {n.id: 0 for n in self.nodes}
        for edge in self.edges:
            adjacency[edge.source].append(edge.target)
            in_degree[edge.target] += 1
        queue = [nid for nid, deg in in_degree.items() if deg == 0]
        order: list[str] = []
        while queue:
            current = queue.pop(0)
            order.append(current)
            for neighbor in adjacency[current]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)
        return order


class WorkflowStore:
    """Persistent store for workflow definitions.

    - In-memory dict for fast access
    - Optional JSON file for persistence (one file per workflow)
    - Thread-safe via asyncio.Lock
    """

    def __init__(self, storage_dir: Path | None = None) -> None:
        self._workflows: dict[str, Workflow] = {}
        self._lock = asyncio.Lock()
        self._storage_dir = storage_dir
        if storage_dir is not None:
            storage_dir.mkdir(parents=True, exist_ok=True)
            self._load_all()

    def _workflow_path(self, workflow_id: str) -> Path:
        if self._storage_dir is None:
            raise RuntimeError("No storage directory configured")
        return self._storage_dir / f"{workflow_id}.json"

    def _load_all(self) -> None:
        """Load all workflows from storage_dir at startup."""
        if self._storage_dir is None:
            return
        for path in self._storage_dir.glob("*.json"):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                workflow = Workflow.from_dict(data)
                self._workflows[workflow.id] = workflow
            except (json.JSONDecodeError, KeyError, ValueError) as e:
                _log.warning("Failed to load workflow from %s: %s", path, e)

    def _persist(self, workflow: Workflow) -> None:
        """Persist a single workflow to disk."""
        if self._storage_dir is None:
            return
        path = self._workflow_path(workflow.id)
        path.write_text(
            json.dumps(workflow.to_dict(), indent=2),
            encoding="utf-8",
        )

    def _delete_persisted(self, workflow_id: str) -> None:
        if self._storage_dir is None:
            return
        path = self._workflow_path(workflow_id)
        if path.exists():
            path.unlink()

    async def create(
        self,
        name: str,
        description: str = "",
        nodes: list[WorkflowNode] | None = None,
        edges: list[WorkflowEdge] | None = None,
        tags: list[str] | None = None,
        workflow_id: str | None = None,
    ) -> Workflow:
        """Create a new workflow. Auto-generates an ID if not provided."""
        async with self._lock:
            wf_id = workflow_id or uuid4().hex[:12]
            workflow = Workflow(
                id=wf_id,
                name=name,
                description=description,
                nodes=nodes or [],
                edges=edges or [],
                tags=tags or [],
            )
            workflow.validate()
            self._workflows[wf_id] = workflow
            self._persist(workflow)
            _log.info("Created workflow '%s' (id=%s)", name, wf_id)
            return workflow

    async def get(self, workflow_id: str) -> Workflow:
        async with self._lock:
            if workflow_id not in self._workflows:
                raise WorkflowNotFoundError(f"Workflow '{workflow_id}' not found")
            return self._workflows[workflow_id]

    async def list(self) -> list[Workflow]:
        async with self._lock:
            return sorted(
                self._workflows.values(),
                key=lambda w: w.updated_at,
                reverse=True,
            )

    async def update(self, workflow_id: str, changes: dict[str, Any]) -> Workflow:
        async with self._lock:
            if workflow_id not in self._workflows:
                raise WorkflowNotFoundError(f"Workflow '{workflow_id}' not found")
            workflow = self._workflows[workflow_id]
            if "name" in changes:
                workflow.name = str(changes["name"])
            if "description" in changes:
                workflow.description = str(changes["description"])
            if "nodes" in changes:
                workflow.nodes = [
                    WorkflowNode.from_dict(n) if isinstance(n, dict) else n
                    for n in changes["nodes"]
                ]
            if "edges" in changes:
                workflow.edges = [
                    WorkflowEdge.from_dict(e) if isinstance(e, dict) else e
                    for e in changes["edges"]
                ]
            if "tags" in changes:
                workflow.tags = list(changes["tags"])
            workflow.updated_at = datetime.now(UTC)
            workflow.validate()
            self._persist(workflow)
            return workflow

    async def delete(self, workflow_id: str) -> bool:
        async with self._lock:
            if workflow_id not in self._workflows:
                return False
            del self._workflows[workflow_id]
            self._delete_persisted(workflow_id)
            return True

    async def add_node(
        self,
        workflow_id: str,
        node: WorkflowNode,
    ) -> Workflow:
        async with self._lock:
            if workflow_id not in self._workflows:
                raise WorkflowNotFoundError(f"Workflow '{workflow_id}' not found")
            workflow = self._workflows[workflow_id]
            workflow.nodes.append(node)
            workflow.updated_at = datetime.now(UTC)
            workflow.validate()
            self._persist(workflow)
            return workflow

    async def add_edge(
        self,
        workflow_id: str,
        edge: WorkflowEdge,
    ) -> Workflow:
        async with self._lock:
            if workflow_id not in self._workflows:
                raise WorkflowNotFoundError(f"Workflow '{workflow_id}' not found")
            workflow = self._workflows[workflow_id]
            workflow.edges.append(edge)
            workflow.updated_at = datetime.now(UTC)
            workflow.validate()
            self._persist(workflow)
            return workflow
