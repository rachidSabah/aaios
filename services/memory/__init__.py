"""Memory subsystem — the unified memory API.

Components:
  - ``manager.py`` — MemoryManager (the unified API: remember, recall, rank,
    summarize, forget, link, context windows)
  - ``embeddings.py`` — EmbeddingsService (wraps a provider, caches results)
  - ``vector_store.py`` — InMemoryVectorStore (cosine similarity search)
  - ``knowledge_graph.py`` — InMemoryKnowledgeGraph (NetworkX-backed)
  - ``ranking.py`` — MemoryRanker (vector + graph + keyword + recency)
  - ``rag.py`` — RAGPipeline (hybrid retrieval + rerank + budget)
  - ``context_window.py`` — ContextWindowManager (per-task bounded context)
  - ``compression.py`` — CompressionScheduler (background summarization)
"""

from __future__ import annotations

from services.memory.compression import CompressionScheduler, SummarizationResult, Summarizer
from services.memory.context_window import ContextWindow, ContextWindowManager
from services.memory.embeddings import (
    EmbeddingsProvider,
    EmbeddingsService,
    LocalEmbeddingsProvider,
)
from services.memory.knowledge_graph import InMemoryKnowledgeGraph
from services.memory.manager import (
    MemoryManager,
    get_memory_manager,
    init_memory_manager,
    set_memory_manager,
)
from services.memory.rag import RAGPipeline
from services.memory.ranking import MemoryRanker, RankConfig
from services.memory.vector_store import InMemoryVectorStore, VectorStoreProtocol

__all__ = [
    "CompressionScheduler",
    "ContextWindow",
    "ContextWindowManager",
    "EmbeddingsProvider",
    "EmbeddingsService",
    "InMemoryKnowledgeGraph",
    "InMemoryVectorStore",
    "LocalEmbeddingsProvider",
    "MemoryManager",
    "MemoryRanker",
    "RAGPipeline",
    "RankConfig",
    "SummarizationResult",
    "Summarizer",
    "VectorStoreProtocol",
    "get_memory_manager",
    "init_memory_manager",
    "set_memory_manager",
]
