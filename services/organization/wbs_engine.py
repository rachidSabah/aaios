"""Work Breakdown Engine — decomposes mission goals into a WBS DAG.

Decomposition hierarchy: program → project → epic → feature → story →
task → subtask. Each level is optional; simple missions may go directly
to tasks.

The engine supports both manual WBS construction (add nodes explicitly)
and automatic decomposition (from a goal + objectives, generate a
default WBS with dependency edges).
"""

from __future__ import annotations

from typing import Any

from core.logging import get_logger
from services.organization.models import (
    Mission,
    MissionPriority,
    WBSNode,
    WBSType,
)

_log = get_logger(__name__)

__all__ = ["WorkBreakdownEngine"]


class WorkBreakdownEngine:
    """Decomposes mission goals into a Work Breakdown Structure.

    Usage:
        engine = WorkBreakdownEngine()
        engine.decompose(mission, strategy="objective_per_project")
        # Or manually:
        engine.add_node(mission, WBSType.TASK, title="Write tests", parent_id=...)
    """

    def decompose(
        self,
        mission: Mission,
        *,
        strategy: str = "objective_per_project",
    ) -> list[WBSNode]:
        """Decompose a mission's objectives into a WBS.

        Strategies:
          - objective_per_project: one project per objective, with
            default epic/task breakdown per project
          - flat: all objectives become direct tasks
          - single_project: one project containing all objectives as tasks
        """
        if strategy == "flat":
            return self._decompose_flat(mission)
        if strategy == "single_project":
            return self._decompose_single_project(mission)
        # Default: objective_per_project
        return self._decompose_objective_per_project(mission)

    def _decompose_flat(self, mission: Mission) -> list[WBSNode]:
        """One task per objective, no hierarchy."""
        nodes: list[WBSNode] = []
        for i, obj in enumerate(mission.objectives):
            node = WBSNode(
                node_type=WBSType.TASK.value,
                title=f"Task: {obj[:80]}",
                description=obj,
                priority=mission.priority,
                depends_on=[nodes[i - 1].node_id] if i > 0 else [],
            )
            mission.wbs_nodes.append(node)
            nodes.append(node)
        _log.info(
            "Decomposed mission '%s' (flat): %d tasks",
            mission.title,
            len(nodes),
        )
        return nodes

    def _decompose_single_project(self, mission: Mission) -> list[WBSNode]:
        """One project containing all objectives as tasks."""
        project = WBSNode(
            node_type=WBSType.PROJECT.value,
            title=f"Project: {mission.title}",
            description=mission.description,
            priority=mission.priority,
        )
        mission.wbs_nodes.append(project)
        nodes: list[WBSNode] = [project]
        for i, obj in enumerate(mission.objectives):
            task = WBSNode(
                parent_id=project.node_id,
                node_type=WBSType.TASK.value,
                title=f"Task {i + 1}: {obj[:80]}",
                description=obj,
                priority=mission.priority,
                depends_on=[nodes[-1].node_id] if i > 0 else [],
            )
            mission.wbs_nodes.append(task)
            nodes.append(task)
        _log.info(
            "Decomposed mission '%s' (single_project): 1 project + %d tasks",
            mission.title,
            len(mission.objectives),
        )
        return nodes

    def _decompose_objective_per_project(self, mission: Mission) -> list[WBSNode]:
        """One project per objective, each with an epic + tasks."""
        nodes: list[WBSNode] = []
        for i, obj in enumerate(mission.objectives):
            # Project
            project = WBSNode(
                node_type=WBSType.PROJECT.value,
                title=f"Project {i + 1}: {obj[:60]}",
                description=f"Project for objective: {obj}",
                priority=mission.priority,
                depends_on=[nodes[-1].node_id]
                if nodes and nodes[-1].node_type == WBSType.PROJECT.value
                else [],
            )
            mission.wbs_nodes.append(project)
            nodes.append(project)

            # Epic
            epic = WBSNode(
                parent_id=project.node_id,
                node_type=WBSType.EPIC.value,
                title=f"Epic: Implement {obj[:60]}",
                description=f"Epic covering all work for: {obj}",
                priority=mission.priority,
            )
            mission.wbs_nodes.append(epic)
            nodes.append(epic)

            # Tasks under the epic
            task_titles = self._suggest_tasks_for_objective(obj)
            prev_task_id: str | None = None
            for title in task_titles:
                task = WBSNode(
                    parent_id=epic.node_id,
                    node_type=WBSType.TASK.value,
                    title=title,
                    description=f"Task: {title}",
                    priority=mission.priority,
                    depends_on=[prev_task_id] if prev_task_id else [],
                    capabilities_required=self._suggest_capabilities(title),
                )
                mission.wbs_nodes.append(task)
                nodes.append(task)
                prev_task_id = task.node_id

        _log.info(
            "Decomposed mission '%s' (objective_per_project): %d nodes",
            mission.title,
            len(nodes),
        )
        return nodes

    def _suggest_tasks_for_objective(self, objective: str) -> list[str]:
        """Suggest task titles for an objective.

        This is a heuristic decomposition. In production, this would call
        the LlmPlanner to generate task breakdowns. For now, we generate
        a standard software-engineering task set.
        """
        return [
            "Research requirements",
            "Design solution",
            "Implement core functionality",
            "Write tests",
            "Document results",
        ]

    def _suggest_capabilities(self, task_title: str) -> list[str]:
        """Suggest capabilities required for a task based on its title."""
        title_lower = task_title.lower()
        caps: list[str] = []
        if "research" in title_lower or "investigate" in title_lower:
            caps.append("research.search")
        if "design" in title_lower or "architect" in title_lower:
            caps.append("code.design")
        if "implement" in title_lower or "code" in title_lower or "write" in title_lower:
            caps.append("code.generate")
        if "test" in title_lower:
            caps.append("code.test")
        if "document" in title_lower or "doc" in title_lower:
            caps.append("code.document")
        if "review" in title_lower:
            caps.append("code.review")
        return caps if caps else ["code.generate"]

    def add_node(
        self,
        mission: Mission,
        node_type: str,
        *,
        title: str,
        description: str = "",
        parent_id: str | None = None,
        depends_on: list[str] | None = None,
        capabilities_required: list[str] | None = None,
        priority: str = MissionPriority.NORMAL.value,
        assigned_agent_id: str | None = None,
        assigned_provider: str | None = None,
        estimated_duration_s: float = 0.0,
        estimated_cost_usd: float = 0.0,
    ) -> WBSNode:
        """Manually add a WBS node to a mission."""
        node = WBSNode(
            node_type=node_type,
            title=title,
            description=description,
            parent_id=parent_id,
            depends_on=depends_on or [],
            capabilities_required=capabilities_required or [],
            priority=priority,
            assigned_agent_id=assigned_agent_id,
            assigned_provider=assigned_provider,
            estimated_duration_s=estimated_duration_s,
            estimated_cost_usd=estimated_cost_usd,
        )
        mission.wbs_nodes.append(node)
        return node

    def add_dependency(
        self,
        mission: Mission,
        node_id: str,
        depends_on_id: str,
    ) -> bool:
        """Add a dependency edge between two WBS nodes."""
        node = mission.get_wbs_node(node_id)
        if node is None:
            return False
        if depends_on_id not in {n.node_id for n in mission.wbs_nodes}:
            return False
        if depends_on_id not in node.depends_on:
            node.depends_on.append(depends_on_id)
        return True

    def validate_dag(self, mission: Mission) -> list[str]:
        """Validate the WBS is a DAG (no cycles). Returns list of errors."""
        errors: list[str] = []
        # Check all depends_on references exist
        node_ids = {n.node_id for n in mission.wbs_nodes}
        for node in mission.wbs_nodes:
            for dep in node.depends_on:
                if dep not in node_ids:
                    errors.append(
                        f"Node '{node.node_id}' depends on non-existent node '{dep}'",
                    )

        # Cycle detection via DFS
        adjacency: dict[str, list[str]] = {n.node_id: list(n.depends_on) for n in mission.wbs_nodes}
        WHITE, GRAY, BLACK = 0, 1, 2
        color: dict[str, int] = dict.fromkeys(node_ids, WHITE)

        def dfs(node: str, path: list[str]) -> bool:
            color[node] = GRAY
            path.append(node)
            for neighbor in adjacency.get(node, []):
                if neighbor not in color:
                    continue
                if color[neighbor] == GRAY:
                    errors.append(f"Cycle detected: {' → '.join(path + [neighbor])}")
                    return True
                if color[neighbor] == WHITE and dfs(neighbor, path):
                    return True
            path.pop()
            color[node] = BLACK
            return False

        for nid in node_ids:
            if color[nid] == WHITE:
                dfs(nid, [])

        return errors

    def topological_order(self, mission: Mission) -> list[str]:
        """Return WBS node IDs in topological order (dependencies first)."""
        errors = self.validate_dag(mission)
        if errors:
            raise ValueError(f"WBS is not a valid DAG: {errors[0]}")
        adjacency: dict[str, list[str]] = {n.node_id: list(n.depends_on) for n in mission.wbs_nodes}
        in_degree: dict[str, int] = {n.node_id: 0 for n in mission.wbs_nodes}
        for node in mission.wbs_nodes:
            for dep in node.depends_on:
                in_degree[node.node_id] += 1
        # Kahn's algorithm
        queue = [nid for nid, deg in in_degree.items() if deg == 0]
        order: list[str] = []
        while queue:
            current = queue.pop(0)
            order.append(current)
            for nid, deps in adjacency.items():
                if current in deps:
                    in_degree[nid] -= 1
                    if in_degree[nid] == 0:
                        queue.append(nid)
        return order

    def get_execution_layers(self, mission: Mission) -> list[list[str]]:
        """Group WBS nodes into execution layers (parallelizable groups).

        Layer 0 = nodes with no dependencies
        Layer N = nodes whose dependencies are all in layers 0..N-1
        """
        errors = self.validate_dag(mission)
        if errors:
            raise ValueError(f"WBS is not a valid DAG: {errors[0]}")
        completed: set[str] = set()
        remaining = {n.node_id for n in mission.wbs_nodes}
        layers: list[list[str]] = []
        while remaining:
            layer = [
                nid
                for nid in remaining
                if all(
                    dep in completed
                    for n in mission.wbs_nodes
                    if n.node_id == nid
                    for dep in n.depends_on
                )
            ]
            if not layer:
                # Shouldn't happen if DAG is valid, but guard against infinite loop
                break
            layers.append(layer)
            completed.update(layer)
            remaining.difference_update(layer)
        return layers

    def merge_tasks(
        self,
        mission: Mission,
        node_id_1: str,
        node_id_2: str,
        *,
        new_title: str | None = None,
    ) -> WBSNode | None:
        """Merge two tasks into one. Returns the merged node, or None on error."""
        n1 = mission.get_wbs_node(node_id_1)
        n2 = mission.get_wbs_node(node_id_2)
        if n1 is None or n2 is None:
            return None
        if n1.node_type != WBSType.TASK.value or n2.node_type != WBSType.TASK.value:
            return None
        # Create merged node
        merged = WBSNode(
            node_type=WBSType.TASK.value,
            title=new_title or f"Merged: {n1.title} + {n2.title}",
            description=f"Merged task: {n1.description} | {n2.description}",
            parent_id=n1.parent_id or n2.parent_id,
            depends_on=list(set(n1.depends_on + n2.depends_on) - {node_id_1, node_id_2}),
            capabilities_required=list(set(n1.capabilities_required + n2.capabilities_required)),
            priority=max(n1.priority, n2.priority),
            estimated_duration_s=max(n1.estimated_duration_s, n2.estimated_duration_s),
            estimated_cost_usd=n1.estimated_cost_usd + n2.estimated_cost_usd,
        )
        # Remove old nodes, add merged
        mission.wbs_nodes = [
            n for n in mission.wbs_nodes if n.node_id not in (node_id_1, node_id_2)
        ]
        mission.wbs_nodes.append(merged)
        # Update any nodes that depended on the old nodes
        for n in mission.wbs_nodes:
            new_deps: list[str] = []
            for dep in n.depends_on:
                if dep in (node_id_1, node_id_2):
                    if merged.node_id not in new_deps:
                        new_deps.append(merged.node_id)
                else:
                    new_deps.append(dep)
            n.depends_on = new_deps
        return merged

    def split_task(
        self,
        mission: Mission,
        node_id: str,
        *,
        sub_tasks: list[dict[str, Any]],
    ) -> list[WBSNode]:
        """Split a task into multiple subtasks. Returns the new subtask nodes."""
        node = mission.get_wbs_node(node_id)
        if node is None:
            return []
        # Create subtasks
        new_nodes: list[WBSNode] = []
        prev_id: str | None = None
        for sub in sub_tasks:
            subtask = WBSNode(
                node_type=WBSType.SUBTASK.value,
                title=sub.get("title", f"Subtask of {node.title}"),
                description=sub.get("description", ""),
                parent_id=node.node_id,
                depends_on=[prev_id] if prev_id else list(node.depends_on),
                capabilities_required=sub.get("capabilities_required", node.capabilities_required),
                priority=node.priority,
                estimated_duration_s=sub.get("estimated_duration_s", 0.0),
                estimated_cost_usd=sub.get("estimated_cost_usd", 0.0),
            )
            mission.wbs_nodes.append(subtask)
            new_nodes.append(subtask)
            prev_id = subtask.node_id
        # Mark original task as having subtasks (it becomes a container)
        node.status = "decomposed"
        return new_nodes
