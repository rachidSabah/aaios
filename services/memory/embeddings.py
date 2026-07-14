"""Embeddings service — generates embedding vectors for text.

Two modes:
  1. Model Router-backed (default for production): uses the configured
     embedding provider (e.g. OpenAI text-embedding-3-small).
  2. Local fallback: uses sentence-transformers (all-MiniLM-L6-v2) for
     offline/low-cost operation. This is the default in tests.

The service is a thin wrapper — it doesn't do caching (that's the Vector
Memory's job) or model selection (that's configured at init time).
"""

from __future__ import annotations

import hashlib
from typing import Protocol

from core.contracts.memory.item import MemoryVector
from core.logging import get_logger

_log = get_logger(__name__)

__all__ = ["EmbeddingsService", "EmbeddingsProvider", "LocalEmbeddingsProvider"]


class EmbeddingsProvider(Protocol):
    """The interface every embeddings provider implements."""

    @property
    def model_name(self) -> str:
        """Return the embedding model name."""
        ...

    @property
    def dimensions(self) -> int:
        """Return the vector dimensionality."""
        ...

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed a batch of texts. Returns one vector per text."""
        ...


class LocalEmbeddingsProvider:
    """A deterministic hash-based embeddings provider for tests.

    NOT for production — produces low-quality embeddings (just hashes).
    The real local provider uses sentence-transformers (Phase 8+ when
    sentence-transformers is installed).
    """

    def __init__(self, dimensions: int = 128) -> None:
        self._dimensions = dimensions

    @property
    def model_name(self) -> str:
        """Return the model name."""
        return "local-hash-128d"

    @property
    def dimensions(self) -> int:
        """Return the dimensionality."""
        return self._dimensions

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed texts using deterministic hashing.

        Each text is hashed, and the hash is expanded to ``dimensions`` floats
        in [0, 1). This is deterministic but produces low-quality embeddings
        (no semantic similarity). Good enough for testing the memory pipeline.
        """
        results: list[list[float]] = []
        for text in texts:
            # Hash the text multiple times to fill the dimensions
            vector: list[float] = []
            for i in range(self._dimensions):
                h = hashlib.sha256(f"{text}:{i}".encode()).hexdigest()
                vector.append(int(h[:8], 16) / 0xFFFFFFFF)
            results.append(vector)
        return results


class EmbeddingsService:
    """The embeddings service — wraps a provider and caches results.

    Usage:
        service = EmbeddingsService(provider=LocalEmbeddingsProvider())
        vector = await service.embed_text('hello world')
        # vector is a MemoryVector
    """

    def __init__(self, provider: EmbeddingsProvider | None = None) -> None:
        self._provider: EmbeddingsProvider = provider or LocalEmbeddingsProvider()
        self._cache: dict[str, MemoryVector] = {}

    @property
    def model_name(self) -> str:
        """Return the model name."""
        return self._provider.model_name

    @property
    def dimensions(self) -> int:
        """Return the dimensionality."""
        return self._provider.dimensions

    async def embed_text(self, text: str) -> MemoryVector:
        """Embed a single text. Returns a MemoryVector."""
        # Cache by text hash
        cache_key = hashlib.sha256(text.encode()).hexdigest()
        if cache_key in self._cache:
            return self._cache[cache_key]
        vectors = await self._provider.embed([text])
        vec = MemoryVector(
            values=vectors[0],
            dimensions=self._provider.dimensions,
            model=self._provider.model_name,
        )
        self._cache[cache_key] = vec
        return vec

    async def embed_batch(self, texts: list[str]) -> list[MemoryVector]:
        """Embed a batch of texts."""
        # Check cache first
        results: list[MemoryVector | None] = [None] * len(texts)
        uncached_indices: list[int] = []
        uncached_texts: list[str] = []
        for i, text in enumerate(texts):
            cache_key = hashlib.sha256(text.encode()).hexdigest()
            if cache_key in self._cache:
                results[i] = self._cache[cache_key]
            else:
                uncached_indices.append(i)
                uncached_texts.append(text)

        if uncached_texts:
            vectors = await self._provider.embed(uncached_texts)
            for idx, vec_values in zip(uncached_indices, vectors, strict=True):
                vec = MemoryVector(
                    values=vec_values,
                    dimensions=self._provider.dimensions,
                    model=self._provider.model_name,
                )
                results[idx] = vec
                cache_key = hashlib.sha256(texts[idx].encode()).hexdigest()
                self._cache[cache_key] = vec

        return [r for r in results if r is not None]

    def clear_cache(self) -> None:
        """Clear the embedding cache."""
        self._cache.clear()
