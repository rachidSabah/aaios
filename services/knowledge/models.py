"""Knowledge Platform models — knowledge entries, memory records, graph nodes.

All models are immutable dataclasses with to_dict() for JSON serialization.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4

__all__ = [
    "AccessLevel",
    "ConflictReport",
    "KnowledgeCollection",
    "KnowledgeEntry",
    "KnowledgeEntryStatus",
    "KnowledgePermission",
    "KnowledgeSearchResult",
    "KnowledgeVersion",
    "KnowledgeWorkspace",
    "MemoryRecord",
    "MemoryScope",
    "MemoryType",
    "RAGResult",
    "RetrievalRequest",
    "StoragePolicy",
]


class MemoryType(StrEnum):
    """15 enterprise memory types."""

    SHORT_TERM = "short_term"
    LONG_TERM = "long_term"
    WORKING = "working"
    SEMANTIC = "semantic"
    PROCEDURAL = "procedural"
    EPISODIC = "episodic"
    PROJECT = "project"
    MISSION = "mission"
    WORKFLOW = "workflow"
    AGENT = "agent"
    PROVIDER = "provider"
    USER = "user"
    ORGANIZATION = "organization"
    EXECUTION = "execution"
    CONVERSATION = "conversation"


class KnowledgeEntryStatus(StrEnum):
    """Knowledge entry lifecycle states."""

    DRAFT = "draft"
    PENDING_REVIEW = "pending_review"
    PUBLISHED = "published"
    ARCHIVED = "archived"
    EXPIRED = "expired"


class AccessLevel(StrEnum):
    """Access levels for knowledge governance."""

    READ = "read"
    WRITE = "write"
    ADMIN = "admin"
    OWNER = "owner"


@dataclass
class StoragePolicy:
    """Storage and retention policy for memory/knowledge."""

    max_age_days: int = 365
    max_entries: int = 100_000
    compress_after_days: int = 30
    encrypt: bool = False
    auto_expire: bool = True
    snapshot_interval_days: int = 7

    def to_dict(self) -> dict[str, Any]:
        return {
            "max_age_days": self.max_age_days,
            "max_entries": self.max_entries,
            "compress_after_days": self.compress_after_days,
            "encrypt": self.encrypt,
            "auto_expire": self.auto_expire,
            "snapshot_interval_days": self.snapshot_interval_days,
        }


@dataclass
class MemoryScope:
    """Scope identifier for a memory record."""

    memory_type: str = MemoryType.LONG_TERM.value
    project_id: str | None = None
    mission_id: str | None = None
    agent_id: str | None = None
    user_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "memory_type": self.memory_type,
            "project_id": self.project_id,
            "mission_id": self.mission_id,
            "agent_id": self.agent_id,
            "user_id": self.user_id,
        }


@dataclass
class MemoryRecord:
    """A record in the enterprise memory system."""

    memory_id: str = field(default_factory=lambda: uuid4().hex[:16])
    memory_type: str = MemoryType.LONG_TERM.value
    scope: MemoryScope = field(default_factory=MemoryScope)
    content: str = ""
    content_type: str = "text"
    embedding: list[float] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)
    importance: float = 0.5
    confidence: float = 0.5
    access_count: int = 0
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    expires_at: datetime | None = None
    version: int = 1
    owner: str | None = None
    encrypted: bool = False
    storage_policy: StoragePolicy = field(default_factory=StoragePolicy)

    def to_dict(self) -> dict[str, Any]:
        return {
            "memory_id": self.memory_id,
            "memory_type": self.memory_type,
            "scope": self.scope.to_dict(),
            "content": self.content[:5000],
            "content_type": self.content_type,
            "metadata": dict(self.metadata),
            "tags": list(self.tags),
            "importance": round(self.importance, 4),
            "confidence": round(self.confidence, 4),
            "access_count": self.access_count,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "version": self.version,
            "owner": self.owner,
            "encrypted": self.encrypted,
            "storage_policy": self.storage_policy.to_dict(),
        }


@dataclass
class KnowledgeEntry:
    """An entry in the knowledge repository."""

    entry_id: str = field(default_factory=lambda: uuid4().hex[:16])
    title: str = ""
    content: str = ""
    content_type: str = "text"
    summary: str = ""
    category: str = ""
    labels: list[str] = field(default_factory=list)
    owner: str | None = None
    status: str = KnowledgeEntryStatus.DRAFT.value
    version: int = 1
    workspace_id: str | None = None
    collection_id: str | None = None
    parent_id: str | None = None
    embedding: list[float] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    quality_score: float = 0.0
    source_confidence: float = 0.5
    freshness_score: float = 1.0
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    published_at: datetime | None = None
    expires_at: datetime | None = None
    reviewed_by: str | None = None
    reviewed_at: datetime | None = None
    access_count: int = 0
    references: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "entry_id": self.entry_id,
            "title": self.title,
            "content": self.content[:10000],
            "content_type": self.content_type,
            "summary": self.summary[:500],
            "category": self.category,
            "labels": list(self.labels),
            "owner": self.owner,
            "status": self.status,
            "version": self.version,
            "workspace_id": self.workspace_id,
            "collection_id": self.collection_id,
            "parent_id": self.parent_id,
            "metadata": dict(self.metadata),
            "quality_score": round(self.quality_score, 4),
            "source_confidence": round(self.source_confidence, 4),
            "freshness_score": round(self.freshness_score, 4),
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "published_at": self.published_at.isoformat() if self.published_at else None,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "reviewed_by": self.reviewed_by,
            "reviewed_at": self.reviewed_at.isoformat() if self.reviewed_at else None,
            "access_count": self.access_count,
            "references": list(self.references),
        }


@dataclass
class KnowledgeVersion:
    """A version of a knowledge entry."""

    version_id: str = field(default_factory=lambda: uuid4().hex[:12])
    entry_id: str = ""
    version: int = 1
    content: str = ""
    title: str = ""
    changed_by: str = "system"
    changed_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    change_reason: str = ""
    hash: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "version_id": self.version_id,
            "entry_id": self.entry_id,
            "version": self.version,
            "content": self.content[:5000],
            "title": self.title,
            "changed_by": self.changed_by,
            "changed_at": self.changed_at.isoformat(),
            "change_reason": self.change_reason,
            "hash": self.hash,
        }


@dataclass
class KnowledgeWorkspace:
    """A knowledge workspace (isolated knowledge space)."""

    workspace_id: str = field(default_factory=lambda: uuid4().hex[:12])
    name: str = ""
    description: str = ""
    owner: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    permissions: list[KnowledgePermission] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "workspace_id": self.workspace_id,
            "name": self.name,
            "description": self.description,
            "owner": self.owner,
            "created_at": self.created_at.isoformat(),
            "permissions": [p.to_dict() for p in self.permissions],
            "metadata": dict(self.metadata),
        }


@dataclass
class KnowledgeCollection:
    """A collection of related knowledge entries."""

    collection_id: str = field(default_factory=lambda: uuid4().hex[:12])
    name: str = ""
    description: str = ""
    workspace_id: str | None = None
    owner: str | None = None
    entry_count: int = 0
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "collection_id": self.collection_id,
            "name": self.name,
            "description": self.description,
            "workspace_id": self.workspace_id,
            "owner": self.owner,
            "entry_count": self.entry_count,
            "created_at": self.created_at.isoformat(),
            "metadata": dict(self.metadata),
        }


@dataclass
class KnowledgePermission:
    """Permission for knowledge governance."""

    principal: str = ""
    principal_type: str = "user"  # user, group, role
    access_level: str = AccessLevel.READ.value
    granted_by: str = "system"
    granted_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, Any]:
        return {
            "principal": self.principal,
            "principal_type": self.principal_type,
            "access_level": self.access_level,
            "granted_by": self.granted_by,
            "granted_at": self.granted_at.isoformat(),
        }


@dataclass
class KnowledgeSearchResult:
    """A single search result from the hybrid search engine."""

    entry_id: str = ""
    title: str = ""
    summary: str = ""
    content_snippet: str = ""
    score: float = 0.0
    match_type: str = "keyword"  # keyword, semantic, graph, fuzzy
    matched_terms: list[str] = field(default_factory=list)
    source: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "entry_id": self.entry_id,
            "title": self.title,
            "summary": self.summary[:200],
            "content_snippet": self.content_snippet[:500],
            "score": round(self.score, 4),
            "match_type": self.match_type,
            "matched_terms": list(self.matched_terms),
            "source": self.source,
        }


@dataclass
class RetrievalRequest:
    """A retrieval request for the RAG engine."""

    query: str = ""
    max_results: int = 10
    workspace_id: str | None = None
    collection_id: str | None = None
    memory_types: list[str] = field(default_factory=list)
    min_confidence: float = 0.0
    min_quality: float = 0.0
    include_citations: bool = True
    deduplicate: bool = True
    context_window_tokens: int = 4096

    def to_dict(self) -> dict[str, Any]:
        return {
            "query": self.query,
            "max_results": self.max_results,
            "workspace_id": self.workspace_id,
            "collection_id": self.collection_id,
            "memory_types": list(self.memory_types),
            "min_confidence": self.min_confidence,
            "min_quality": self.min_quality,
            "include_citations": self.include_citations,
            "deduplicate": self.deduplicate,
            "context_window_tokens": self.context_window_tokens,
        }


@dataclass
class RAGResult:
    """A retrieval-augmented generation result."""

    query: str = ""
    context: str = ""
    citations: list[dict[str, Any]] = field(default_factory=list)
    sources: list[str] = field(default_factory=list)
    confidence: float = 0.0
    token_count: int = 0
    conflicts: list[dict[str, Any]] = field(default_factory=list)
    freshness_score: float = 1.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "query": self.query,
            "context": self.context[:10000],
            "citations": list(self.citations),
            "sources": list(self.sources),
            "confidence": round(self.confidence, 4),
            "token_count": self.token_count,
            "conflicts": list(self.conflicts),
            "freshness_score": round(self.freshness_score, 4),
        }


@dataclass
class ConflictReport:
    """A knowledge conflict detection report."""

    conflict_id: str = field(default_factory=lambda: uuid4().hex[:12])
    entry_ids: list[str] = field(default_factory=list)
    conflict_type: str = ""  # factual, temporal, source
    description: str = ""
    resolution: str = ""
    detected_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, Any]:
        return {
            "conflict_id": self.conflict_id,
            "entry_ids": list(self.entry_ids),
            "conflict_type": self.conflict_type,
            "description": self.description,
            "resolution": self.resolution,
            "detected_at": self.detected_at.isoformat(),
        }
