"""Vector Memory — vector storage and similarity search.

Two implementations:
  1. InMemoryVectorStore (default for tests and ephemeral runs)
  2. QdrantVectorStore (production; connects to a Qdrant server)

Both implement the VectorStoreProtocol. The Memory Manager doesn't know
which one is in use.
"""

from __future__ import annotations

import asyncio
import math
from typing import Protocol

from core.contracts.memory.item import MemoryItem
from core.logging import get_logger

_log = get_logger(__name__)

__all__ = ["InMemoryVectorStore", "VectorStoreProtocol"]


class VectorStoreProtocol(Protocol):
    """The interface every vector store implements."""

    async def upsert(self, collection: str, items: list[MemoryItem]) -> None:
        """Insert or update items (with their embeddings) in the collection."""
        ...

    async def search(
        self,
        collection: str,
        query_vector: list[float],
        k: int = 10,
        filter: dict[str, str] | None = None,
    ) -> list[tuple[MemoryItem, float]]:
        """Search for similar items. Returns (item, score) pairs."""
        ...

    async def delete(self, collection: str, item_ids: list[str]) -> None:
        """Delete items by ID."""
        ...

    async def count(self, collection: str) -> int:
        """Return the number of items in the collection."""
        ...

    async def list_collections(self) -> list[str]:
        """Return all collection names."""
        ...

    async def delete_collection(self, collection: str) -> None:
        """Delete an entire collection."""
        ...


class InMemoryVectorStore:
    """In-memory vector store with cosine similarity.

    Not durable across process restarts. Use QdrantVectorStore for production.
    """

    def __init__(self) -> None:
        # collection -> {item_id -> (MemoryItem, vector_values)}
        self._collections: dict[str, dict[str, tuple[MemoryItem, list[float]]]] = {}
        self._lock = asyncio.Lock()

    async def upsert(self, collection: str, items: list[MemoryItem]) -> None:
        """Insert or update items."""
        async with self._lock:
            if collection not in self._collections:
                self._collections[collection] = {}
            for item in items:
                if item.embedding is None:
                    _log.warning("vector_store.upsert_no_embedding", item_id=str(item.id))
                    continue
                self._collections[collection][str(item.id)] = (item, item.embedding.values)

    async def search(
        self,
        collection: str,
        query_vector: list[float],
        k: int = 10,
        filter: dict[str, str] | None = None,
    ) -> list[tuple[MemoryItem, float]]:
        """Search for similar items using cosine similarity."""
        async with self._lock:
            col = self._collections.get(collection, {})
            if not col:
                return []
            results: list[tuple[MemoryItem, float]] = []
            for item, vec in col.values():
                # Apply metadata filter
                if filter:
                    if not all(item.metadata.get(k) == v for k, v in filter.items()):
                        continue
                score = _cosine_similarity(query_vector, vec)
                results.append((item, score))
            # Sort by score descending, take top k
            results.sort(key=lambda x: x[1], reverse=True)
            return results[:k]

    async def delete(self, collection: str, item_ids: list[str]) -> None:
        """Delete items by ID."""
        async with self._lock:
            col = self._collections.get(collection, {})
            for item_id in item_ids:
                col.pop(item_id, None)

    async def count(self, collection: str) -> int:
        """Return the number of items."""
        async with self._lock:
            return len(self._collections.get(collection, {}))

    async def list_collections(self) -> list[str]:
        """Return all collection names."""
        async with self._lock:
            return list(self._collections.keys())

    async def delete_collection(self, collection: str) -> None:
        """Delete a collection."""
        async with self._lock:
            self._collections.pop(collection, None)


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    """Compute cosine similarity between two vectors."""
    if len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    mag_a = math.sqrt(sum(x * x for x in a))
    mag_b = math.sqrt(sum(y * y for y in b))
    if mag_a == 0 or mag_b == 0:
        return 0.0
    return dot / (mag_a * mag_b)
