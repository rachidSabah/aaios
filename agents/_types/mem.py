"""MemoryAgent — memory operations."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from agents._types.gen import GenericAgent


@runtime_checkable
class MemoryAgent(GenericAgent, Protocol):
    """The Memory agent type.

    Capabilities advertised: ``memory.recall``, ``memory.summarize``,
    ``memory.forget``, ``memory.link``, ``memory.rank``.

    Wraps the Memory Manager service for agents that need to manipulate
    memory directly.
    """

    async def recall(self, scope: str, query: str, k: int = 10) -> Any:  # returns RecallResult
        """Recall the top-k items from a memory scope matching the query."""
        ...

    async def summarize(self, scope: str) -> str:
        """Summarize a memory scope into a compact representation."""
        ...

    async def forget(self, scope: str, filter: dict[str, Any]) -> int:
        """Forget items matching the filter. Returns count removed."""
        ...

    async def link(self, from_id: str, to_id: str, relation: str) -> None:
        """Link two memory items with a relation."""
        ...

    async def rank(self, items: list[Any], query: str) -> list[Any]:
        """Rank items by relevance to the query."""
        ...
