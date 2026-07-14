"""MemoryItem — the universal unit of memory.

A MemoryItem is anything the system remembers: a conversation turn, a
project decision, a learned fact, a code snippet, a web search result.

Each item has:
  - A unique id (UUID)
  - A scope (short_term, long_term, semantic, conversation, project)
  - Content (the text or structured data)
  - Metadata (tags, timestamps, source, etc.)
  - An optional embedding vector (for vector similarity search)
  - A relevance score (set during recall/ranking)
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

from core.contracts.timestamp import utc_now

__all__ = ["MemoryItem", "MemoryScope", "MemoryScopeType", "MemoryVector"]


class MemoryScopeType(StrEnum):
    """The 5 memory scope types."""

    SHORT_TERM = "short_term"  # current task context, cleared on completion
    LONG_TERM = "long_term"  # persistent facts learned across tasks
    SEMANTIC = "semantic"  # meaning-based (embeddings), cross-scope
    CONVERSATION = "conversation"  # per-conversation history
    PROJECT = "project"  # per-project facts, decisions, artifacts


class MemoryScope(BaseModel):
    """Identifies a memory scope (type + optional project/conversation ID)."""

    model_config = ConfigDict(frozen=True)

    scope_type: MemoryScopeType
    project_id: str | None = None
    conversation_id: str | None = None

    def __str__(self) -> str:
        """Compact string form for use as a dict key."""
        parts = [self.scope_type.value]
        if self.project_id:
            parts.append(f"project={self.project_id}")
        if self.conversation_id:
            parts.append(f"conv={self.conversation_id}")
        return ":".join(parts)


class MemoryVector(BaseModel):
    """An embedding vector with its dimensionality."""

    model_config = ConfigDict(frozen=True)

    values: list[float]
    dimensions: int = Field(description="Number of dimensions (e.g. 1536).")
    model: str = Field(default="", description="Embedding model used.")

    def __len__(self) -> int:
        """Return the vector length."""
        return len(self.values)


class MemoryItem(BaseModel):
    """A single memory item.

    The ``content`` is the primary payload (text or structured data).
    The ``embedding`` is set by the embeddings service for vector search.
    The ``score`` is set during recall/ranking (0.0 = irrelevant, 1.0 = perfect match).
    """

    model_config = ConfigDict(extra="forbid")

    id: UUID = Field(default_factory=uuid4)
    scope: MemoryScope
    content: str = Field(description="The text or JSON-serialized content.")
    content_type: str = Field(default="text", description="text, json, markdown, code")
    metadata: dict[str, Any] = Field(default_factory=dict)
    embedding: MemoryVector | None = Field(default=None)
    score: float = Field(
        default=0.0, ge=0.0, le=1.0, description="Relevance score (set during recall)."
    )
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    # For compression: if this item is a summary of other items
    summarizes: list[UUID] = Field(
        default_factory=list, description="IDs of items this summarizes."
    )
    # Expiration (for short-term memory)
    expires_at: datetime | None = Field(default=None)

    @classmethod
    def create(
        cls,
        scope: MemoryScope,
        content: str,
        *,
        content_type: str = "text",
        metadata: dict[str, Any] | None = None,
    ) -> MemoryItem:
        """Create a new memory item."""
        return cls(
            scope=scope,
            content=content,
            content_type=content_type,
            metadata=metadata or {},
        )

    def is_expired(self, now: datetime | None = None) -> bool:
        """Return True if this item has expired."""
        if self.expires_at is None:
            return False
        now = now or utc_now()
        return now >= self.expires_at
