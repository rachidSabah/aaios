"""Knowledge Graph — entity-relationship storage and graph queries.

Default implementation: InMemoryKnowledgeGraph (NetworkX-backed).
Optional adapter: Neo4jKnowledgeGraph (Phase 8+).

The graph stores entities (nodes) and relationships (edges). The RAG
pipeline uses graph traversal to find items that are topologically close
to high-relevance vector search results — catching connections that
textual similarity alone would miss.
"""

from __future__ import annotations

from collections import deque
from uuid import UUID

import networkx as nx

from core.contracts.memory.graph import GraphEdge, GraphNode
from core.logging import get_logger

_log = get_logger(__name__)

__all__ = ["InMemoryKnowledgeGraph"]


class InMemoryKnowledgeGraph:
    """NetworkX-backed knowledge graph (in-process)."""

    def __init__(self) -> None:
        self._graph: nx.DiGraph = nx.DiGraph()
        self._nodes: dict[UUID, GraphNode] = {}

    async def add_node(self, node: GraphNode) -> UUID:
        """Add a node."""
        self._nodes[node.id] = node
        self._graph.add_node(
            node.id,
            entity_type=node.entity_type,
            name=node.name,
            **node.properties,
        )
        _log.debug(
            "graph.node_added", node_id=str(node.id), name=node.name, entity_type=node.entity_type
        )
        return node.id

    async def add_edge(self, edge: GraphEdge) -> None:
        """Add an edge."""
        self._graph.add_edge(
            edge.source_id,
            edge.target_id,
            relation=edge.relation,
            weight=edge.weight,
            **edge.properties,
        )
        _log.debug(
            "graph.edge_added",
            source=str(edge.source_id),
            target=str(edge.target_id),
            relation=edge.relation,
        )

    async def get_node(self, node_id: UUID) -> GraphNode | None:
        """Return a node, or None."""
        return self._nodes.get(node_id)

    async def find_nodes(
        self,
        name: str | None = None,
        entity_type: str | None = None,
    ) -> list[GraphNode]:
        """Find nodes by name and/or type."""
        results: list[GraphNode] = []
        for node in self._nodes.values():
            if name is not None and node.name != name:
                continue
            if entity_type is not None and node.entity_type != entity_type:
                continue
            results.append(node)
        return results

    async def neighbors(
        self,
        node_id: UUID,
        *,
        max_depth: int = 1,
        relation: str | None = None,
    ) -> list[tuple[GraphNode, GraphEdge]]:
        """Return neighbors of a node (BFS up to max_depth).

        Returns (neighbor_node, edge) pairs.
        """
        if node_id not in self._graph:
            return []
        results: list[tuple[GraphNode, GraphEdge]] = []
        visited: set[UUID] = {node_id}
        queue: deque[tuple[UUID, int]] = deque([(node_id, 0)])
        while queue:
            current, depth = queue.popleft()
            if depth >= max_depth:
                continue
            for neighbor_id in self._graph.neighbors(current):
                if neighbor_id in visited:
                    continue
                visited.add(neighbor_id)
                edge_data = self._graph.edges[current, neighbor_id]
                edge_relation = edge_data.get("relation", "")
                if relation is not None and edge_relation != relation:
                    continue
                neighbor_node = self._nodes.get(neighbor_id)
                if neighbor_node is None:
                    continue
                edge = GraphEdge(
                    source_id=current,
                    target_id=neighbor_id,
                    relation=edge_relation,
                    weight=edge_data.get("weight", 1.0),
                )
                results.append((neighbor_node, edge))
                queue.append((neighbor_id, depth + 1))
        return results

    async def query(self, pattern: dict[str, Any]) -> list[GraphNode]:  # type: ignore[name-defined]
        """Query nodes by property pattern."""
        results: list[GraphNode] = []
        for node in self._nodes.values():
            match = True
            for key, value in pattern.items():
                if key == "entity_type":
                    if node.entity_type != value:
                        match = False
                        break
                elif key == "name":
                    if node.name != value:
                        match = False
                        break
                elif node.properties.get(key) != value:
                    match = False
                    break
            if match:
                results.append(node)
        return results

    async def delete_node(self, node_id: UUID) -> bool:
        """Delete a node and its edges."""
        if node_id not in self._nodes:
            return False
        del self._nodes[node_id]
        self._graph.remove_node(node_id)
        return True

    async def node_count(self) -> int:
        """Return the total node count."""
        return len(self._nodes)

    async def edge_count(self) -> int:
        """Return the total edge count."""
        return int(self._graph.number_of_edges())

    def get_subgraph(self, node_ids: list[UUID], *, max_depth: int = 1) -> nx.DiGraph:
        """Return a subgraph around the given nodes (for visualization)."""
        result = nx.DiGraph()
        visited: set[UUID] = set()
        queue: deque[tuple[UUID, int]] = deque((nid, 0) for nid in node_ids)
        while queue:
            current, depth = queue.popleft()
            if current in visited or depth > max_depth:
                continue
            visited.add(current)
            node = self._nodes.get(current)
            if node:
                result.add_node(
                    current, **node.properties, name=node.name, entity_type=node.entity_type
                )
            for neighbor in self._graph.neighbors(current):
                if neighbor not in visited:
                    edge_data = self._graph.edges[current, neighbor]
                    result.add_edge(current, neighbor, **edge_data)
                    queue.append((neighbor, depth + 1))
        return result
