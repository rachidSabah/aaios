"""Knowledge Graph contracts — nodes, edges, and the graph protocol."""

from __future__ import annotations

from typing import Any, Protocol
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

__all__ = ["GraphEdge", "GraphNode", "KnowledgeGraphProtocol"]


class GraphNode(BaseModel):
    """A node in the knowledge graph (an entity, concept, or memory item)."""

    model_config = ConfigDict(frozen=True)

    id: UUID = Field(default_factory=uuid4)
    entity_type: str = Field(description='e.g. "person", "project", "decision", "code_module".')
    name: str = Field(description="Display name.")
    properties: dict[str, Any] = Field(default_factory=dict)
    # Link back to the memory item this node represents (if any)
    memory_item_id: UUID | None = None


class GraphEdge(BaseModel):
    """An edge in the knowledge graph (a relationship between nodes)."""

    model_config = ConfigDict(frozen=True)

    source_id: UUID
    target_id: UUID
    relation: str = Field(description='e.g. "decided_by", "depends_on", "part_of".')
    properties: dict[str, Any] = Field(default_factory=dict)
    weight: float = Field(default=1.0, ge=0.0)


class KnowledgeGraphProtocol(Protocol):
    """The interface every knowledge graph implementation satisfies.

    Implementations:
      - InMemoryKnowledgeGraph (default; NetworkX-backed)
      - Neo4jKnowledgeGraph (optional adapter, Phase 8+)
    """

    async def add_node(self, node: GraphNode) -> UUID:
        """Add a node. Returns the node ID."""
        ...

    async def add_edge(self, edge: GraphEdge) -> None:
        """Add an edge."""
        ...

    async def get_node(self, node_id: UUID) -> GraphNode | None:
        """Return a node, or None."""
        ...

    async def find_nodes(
        self, name: str | None = None, entity_type: str | None = None
    ) -> list[GraphNode]:
        """Find nodes by name and/or type."""
        ...

    async def neighbors(
        self,
        node_id: UUID,
        *,
        max_depth: int = 1,
        relation: str | None = None,
    ) -> list[tuple[GraphNode, GraphEdge]]:
        """Return neighbors of a node (BFS up to max_depth)."""
        ...

    async def query(self, pattern: dict[str, Any]) -> list[GraphNode]:
        """Query nodes by property pattern."""
        ...

    async def delete_node(self, node_id: UUID) -> bool:
        """Delete a node and its edges. Returns True if found."""
        ...

    async def node_count(self) -> int:
        """Return the total node count."""
        ...

    async def edge_count(self) -> int:
        """Return the total edge count."""
        ...
