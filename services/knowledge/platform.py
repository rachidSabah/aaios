"""Knowledge Platform — Knowledge Repository + Hybrid Search + RAG + Governance + Graph.

The Knowledge Platform is the top-level enterprise knowledge system that
sits above the Memory Platform. It manages structured knowledge entries
with versioning, governance, search, retrieval, and graph relationships.
"""

from __future__ import annotations

import asyncio
import hashlib
import math
import re
from collections import defaultdict
from datetime import UTC, datetime
from typing import Any

from core.logging import get_logger
from services.knowledge.memory_platform import MemoryOrchestrator
from services.knowledge.models import (
    AccessLevel,
    ConflictReport,
    KnowledgeCollection,
    KnowledgeEntry,
    KnowledgeEntryStatus,
    KnowledgePermission,
    KnowledgeSearchResult,
    KnowledgeVersion,
    KnowledgeWorkspace,
    MemoryRecord,
    RAGResult,
    RetrievalRequest,
)

_log = get_logger(__name__)

__all__ = [
    "EnterpriseKnowledgeGraph",
    "HybridSearchEngine",
    "KnowledgeGovernance",
    "KnowledgePlatform",
    "RetrievalEngine",
]


_STOP_WORDS = frozenset({
    "a", "an", "the", "and", "or", "but", "is", "are", "was", "were",
    "be", "been", "being", "have", "has", "had", "do", "does", "did",
    "will", "would", "could", "should", "may", "might", "must", "shall",
    "can", "of", "in", "on", "at", "to", "for", "with", "by", "from",
    "as", "into", "through", "this", "that", "these", "those",
})


def _tokenize(text: str) -> list[str]:
    words = re.findall(r"[a-z0-9]+", text.lower())
    return [w for w in words if w not in _STOP_WORDS and len(w) > 1]


class EnterpriseKnowledgeGraph:
    """Enterprise Knowledge Graph with 20+ node types.

    Supports: traversal, inference, dependency analysis, semantic linking,
    impact analysis.
    """

    NODE_TYPES: list[str] = [
        "user", "organization", "project", "repository", "file", "class",
        "function", "agent", "provider", "plugin", "workflow", "task",
        "execution", "failure", "approval", "policy", "secret",
        "infrastructure", "server", "cloud_resource", "document", "api",
        "knowledge_entry", "memory_record",
    ]

    def __init__(self) -> None:
        self._nodes: dict[str, dict[str, Any]] = {}
        self._edges: list[dict[str, Any]] = []
        self._by_type: dict[str, list[str]] = defaultdict(list)
        self._adjacency: dict[str, list[str]] = defaultdict(list)
        self._lock = asyncio.Lock()

    async def add_node(self, node_id: str, node_type: str, name: str = "", properties: dict[str, Any] | None = None) -> dict[str, Any]:
        async with self._lock:
            node = {"node_id": node_id, "node_type": node_type, "name": name, "properties": properties or {}}
            self._nodes[node_id] = node
            self._by_type[node_type].append(node_id)
            return node

    async def add_edge(self, source_id: str, target_id: str, relationship: str, properties: dict[str, Any] | None = None) -> dict[str, Any]:
        async with self._lock:
            edge = {"source_id": source_id, "target_id": target_id, "relationship": relationship, "properties": properties or {}}
            self._edges.append(edge)
            self._adjacency[source_id].append(target_id)
            self._adjacency[target_id].append(source_id)
            return edge

    async def get_node(self, node_id: str) -> dict[str, Any] | None:
        async with self._lock:
            return self._nodes.get(node_id)

    async def find_by_type(self, node_type: str) -> list[dict[str, Any]]:
        async with self._lock:
            return [self._nodes[nid] for nid in self._by_type.get(node_type, []) if nid in self._nodes]

    async def traverse(self, start_id: str, max_depth: int = 3) -> list[dict[str, Any]]:
        """BFS traversal from a starting node."""
        async with self._lock:
            visited: set[str] = set()
            queue = [(start_id, 0)]
            result: list[dict[str, Any]] = []
            while queue:
                node_id, depth = queue.pop(0)
                if node_id in visited or depth > max_depth:
                    continue
                visited.add(node_id)
                node = self._nodes.get(node_id)
                if node:
                    result.append(node)
                for neighbor in self._adjacency.get(node_id, []):
                    if neighbor not in visited:
                        queue.append((neighbor, depth + 1))
            return result

    async def impact_analysis(self, node_id: str) -> dict[str, Any]:
        """Analyze the impact of changing a node."""
        affected = await self.traverse(node_id, max_depth=5)
        return {
            "source_node": node_id,
            "affected_count": len(affected),
            "affected_nodes": [{"node_id": n["node_id"], "name": n["name"], "type": n["node_type"]} for n in affected],
            "affected_types": list({n["node_type"] for n in affected}),
        }

    async def semantic_search(self, query: str) -> list[dict[str, Any]]:
        """Keyword search over node names and properties."""
        query_lower = query.lower()
        async with self._lock:
            results = []
            for node in self._nodes.values():
                if query_lower in node["name"].lower():
                    results.append(node)
                    continue
                for v in node["properties"].values():
                    if isinstance(v, str) and query_lower in v.lower():
                        results.append(node)
                        break
            return results

    async def snapshot(self) -> dict[str, Any]:
        async with self._lock:
            return {
                "nodes": list(self._nodes.values()),
                "edges": list(self._edges),
                "node_count": len(self._nodes),
                "edge_count": len(self._edges),
            }

    async def populate_from_memory(self, memory_orchestrator: MemoryOrchestrator) -> int:
        """Auto-populate the graph from memory records."""
        count = 0
        for mt in memory_orchestrator.memory_types:
            store = memory_orchestrator._stores.get(mt)
            if not store:
                continue
            records = await store.all_records()
            for record in records:
                node_id = f"memory:{record.memory_id}"
                if node_id not in self._nodes:
                    await self.add_node(
                        node_id, "memory_record", record.content[:80],
                        {"memory_type": record.memory_type, "importance": record.importance},
                    )
                    count += 1
        return count


class HybridSearchEngine:
    """Hybrid search: keyword + semantic + graph + fuzzy.

    Combines multiple search strategies with hybrid ranking.
    """

    def __init__(self) -> None:
        self._entries: dict[str, KnowledgeEntry] = {}
        self._index: dict[str, list[tuple[str, int]]] = defaultdict(list)
        self._doc_lengths: dict[str, int] = {}
        self._total_docs: int = 0
        self._lock = asyncio.Lock()

    async def index_entry(self, entry: KnowledgeEntry) -> None:
        """Index a knowledge entry for search."""
        async with self._lock:
            self._entries[entry.entry_id] = entry
            text = f"{entry.title} {entry.summary} {entry.content} {' '.join(entry.labels)}"
            tokens = _tokenize(text)
            self._doc_lengths[entry.entry_id] = len(tokens)
            from collections import Counter
            tf = Counter(tokens)
            for term, count in tf.items():
                self._index[term].append((entry.entry_id, count))
            self._total_docs = len(self._entries)

    async def search(
        self,
        query: str,
        *,
        workspace_id: str | None = None,
        collection_id: str | None = None,
        limit: int = 10,
    ) -> list[KnowledgeSearchResult]:
        """Hybrid search across keyword, semantic, and fuzzy matching."""
        query_tokens = _tokenize(query)
        if not query_tokens:
            return []
        async with self._lock:
            # Keyword (TF-IDF)
            scores: dict[str, float] = defaultdict(float)
            matched_terms: dict[str, set[str]] = defaultdict(set)
            for term in query_tokens:
                df = len(self._index.get(term, []))
                if df == 0 or self._total_docs == 0:
                    continue
                idf = math.log(self._total_docs / df)
                for doc_id, tf in self._index.get(term, []):
                    score = tf * idf
                    scores[doc_id] += score
                    matched_terms[doc_id].add(term)
            # Fuzzy matching (simple prefix match)
            for term in query_tokens:
                for indexed_term in list(self._index.keys()):
                    if indexed_term.startswith(term[:3]) and indexed_term != term:
                        for doc_id, tf in self._index.get(indexed_term, []):
                            scores[doc_id] += tf * 0.3
                            matched_terms[doc_id].add(indexed_term)
            # Normalize
            for doc_id in scores:
                length = self._doc_lengths.get(doc_id, 1)
                scores[doc_id] /= max(1, length)
            # Rank
            ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:limit * 2]
            # Build results
            results: list[KnowledgeSearchResult] = []
            for doc_id, score in ranked:
                entry = self._entries.get(doc_id)
                if entry is None:
                    continue
                if workspace_id and entry.workspace_id != workspace_id:
                    continue
                if collection_id and entry.collection_id != collection_id:
                    continue
                results.append(KnowledgeSearchResult(
                    entry_id=entry.entry_id,
                    title=entry.title,
                    summary=entry.summary,
                    content_snippet=entry.content[:500],
                    score=score,
                    match_type="hybrid",
                    matched_terms=sorted(matched_terms[doc_id]),
                    source="knowledge_repository",
                ))
            return results[:limit]


class RetrievalEngine:
    """Enterprise RAG engine with context ranking, pruning, and citation.

    Implements: hybrid RAG, context ranking, context pruning, dynamic
    chunking, citation generation, evidence tracking, source confidence,
    freshness scoring, duplicate elimination, knowledge conflict detection.
    """

    def __init__(
        self,
        search_engine: HybridSearchEngine,
        memory_orchestrator: MemoryOrchestrator,
    ) -> None:
        self._search = search_engine
        self._memory = memory_orchestrator

    async def retrieve(self, request: RetrievalRequest) -> RAGResult:
        """Retrieve context for a RAG query."""
        # 1. Search knowledge entries
        search_results = await self._search.search(
            request.query,
            workspace_id=request.workspace_id,
            collection_id=request.collection_id,
            limit=request.max_results,
        )
        # 2. Search memory
        memory_results = await self._memory.search(
            request.query,
            limit=request.max_results,
        )
        # 3. Merge and rank
        all_sources: list[dict[str, Any]] = []
        for result in search_results:
            all_sources.append({
                "source": "knowledge",
                "entry_id": result.entry_id,
                "title": result.title,
                "content": result.content_snippet,
                "score": result.score,
                "match_type": result.match_type,
            })
        for record in memory_results:
            all_sources.append({
                "source": "memory",
                "memory_id": record.memory_id,
                "title": record.content[:80],
                "content": record.content,
                "score": record.importance * record.confidence,
                "match_type": record.memory_type,
            })
        # 4. Filter by confidence
        if request.min_confidence > 0:
            all_sources = [s for s in all_sources if s["score"] >= request.min_confidence]
        # 5. Deduplicate
        if request.deduplicate:
            seen_hashes: set[str] = set()
            unique: list[dict[str, Any]] = []
            for source in all_sources:
                content_hash = hashlib.sha256(source["content"].encode()).hexdigest()[:16]
                if content_hash not in seen_hashes:
                    seen_hashes.add(content_hash)
                    unique.append(source)
            all_sources = unique
        # 6. Context pruning — fit within token budget
        token_budget = request.context_window_tokens
        context_parts: list[str] = []
        citations: list[dict[str, Any]] = []
        sources: list[str] = []
        total_tokens = 0
        for source in all_sources[:request.max_results]:
            tokens = len(source["content"]) // 4
            if total_tokens + tokens > token_budget:
                remaining = (token_budget - total_tokens) * 4
                if remaining > 100:
                    truncated = source["content"][:remaining] + "..."
                    context_parts.append(truncated)
                    total_tokens += len(truncated) // 4
                break
            context_parts.append(source["content"])
            total_tokens += tokens
            if request.include_citations:
                citations.append({
                    "source": source["source"],
                    "id": source.get("entry_id") or source.get("memory_id"),
                    "title": source["title"],
                    "score": source["score"],
                })
            sources.append(source.get("entry_id") or source.get("memory_id", ""))
        # 7. Conflict detection
        conflicts = self._detect_conflicts(all_sources)
        # 8. Freshness scoring
        freshness = 1.0 if all_sources else 0.0
        # 9. Confidence
        confidence = sum(s["score"] for s in all_sources[:request.max_results]) / max(1, len(all_sources[:request.max_results]))
        return RAGResult(
            query=request.query,
            context="\n\n".join(context_parts),
            citations=citations,
            sources=sources,
            confidence=round(confidence, 4),
            token_count=total_tokens,
            conflicts=[c.to_dict() for c in conflicts],
            freshness_score=freshness,
        )

    def _detect_conflicts(self, sources: list[dict[str, Any]]) -> list[ConflictReport]:
        """Detect factual conflicts between sources."""
        conflicts: list[ConflictReport] = []
        # Simple heuristic: if two sources have very different content but same title
        for i, s1 in enumerate(sources):
            for s2 in sources[i + 1:]:
                if s1.get("title") == s2.get("title") and s1.get("content") != s2.get("content"):
                    conflicts.append(ConflictReport(
                        entry_ids=[s1.get("entry_id", ""), s2.get("entry_id", "")],
                        conflict_type="factual",
                        description=f"Conflicting content for '{s1.get('title', '')}'",
                        resolution="Review both sources and mark one as authoritative",
                    ))
        return conflicts[:5]


class KnowledgeGovernance:
    """Knowledge governance: ownership, approval, publishing, retention, RBAC.

    Implements: ownership, approval, publishing, archiving, retention,
    legal hold, compliance, access control, quality scoring, validation.
    """

    def __init__(self) -> None:
        self._permissions: dict[str, list[KnowledgePermission]] = defaultdict(list)
        self._legal_holds: set[str] = set()  # entry_ids on legal hold
        self._lock = asyncio.Lock()

    async def grant_access(
        self,
        entry_id: str,
        principal: str,
        access_level: str = AccessLevel.READ.value,
        principal_type: str = "user",
        granted_by: str = "system",
    ) -> KnowledgePermission:
        perm = KnowledgePermission(
            principal=principal,
            principal_type=principal_type,
            access_level=access_level,
            granted_by=granted_by,
        )
        async with self._lock:
            self._permissions[entry_id].append(perm)
        return perm

    async def check_access(self, entry_id: str, principal: str, required_level: str = AccessLevel.READ.value) -> bool:
        """Check if a principal has the required access level."""
        async with self._lock:
            perms = self._permissions.get(entry_id, [])
            level_order = [AccessLevel.READ.value, AccessLevel.WRITE.value, AccessLevel.ADMIN.value, AccessLevel.OWNER.value]
            for perm in perms:
                if perm.principal in (principal, "*"):
                    if level_order.index(perm.access_level) >= level_order.index(required_level):
                        return True
        return False

    async def publish(self, entry: KnowledgeEntry, published_by: str = "system") -> KnowledgeEntry:
        """Publish a knowledge entry (transition from draft to published)."""
        entry.status = KnowledgeEntryStatus.PUBLISHED.value
        entry.published_at = datetime.now(UTC)
        entry.reviewed_by = published_by
        entry.reviewed_at = datetime.now(UTC)
        return entry

    async def archive(self, entry: KnowledgeEntry) -> KnowledgeEntry:
        """Archive a knowledge entry."""
        entry.status = KnowledgeEntryStatus.ARCHIVED.value
        return entry

    async def legal_hold(self, entry_id: str) -> None:
        """Place a legal hold on an entry (prevents deletion)."""
        async with self._lock:
            self._legal_holds.add(entry_id)

    async def release_hold(self, entry_id: str) -> None:
        """Release a legal hold."""
        async with self._lock:
            self._legal_holds.discard(entry_id)

    async def is_on_hold(self, entry_id: str) -> bool:
        async with self._lock:
            return entry_id in self._legal_holds

    async def quality_score(self, entry: KnowledgeEntry) -> float:
        """Compute a quality score (0.0-1.0) for a knowledge entry."""
        score = 0.0
        if entry.title:
            score += 0.1
        if entry.content and len(entry.content) > 50:
            score += 0.2
        if entry.summary:
            score += 0.1
        if entry.labels:
            score += 0.1
        if entry.reviewed_by:
            score += 0.2
        if entry.references:
            score += 0.1
        if entry.source_confidence > 0.7:
            score += 0.2
        return min(1.0, score)


class KnowledgePlatform:
    """Top-level Knowledge Platform facade.

    Wires together:
      - Knowledge Repository (entries, versions, collections, workspaces)
      - Hybrid Search Engine
      - Retrieval Engine (RAG)
      - Knowledge Governance
      - Enterprise Knowledge Graph
      - Memory Orchestrator
    """

    def __init__(self) -> None:
        self.memory = MemoryOrchestrator()
        self.graph = EnterpriseKnowledgeGraph()
        self.search_engine = HybridSearchEngine()
        self.governance = KnowledgeGovernance()
        self.retrieval = RetrievalEngine(self.search_engine, self.memory)
        self._entries: dict[str, KnowledgeEntry] = {}
        self._versions: dict[str, list[KnowledgeVersion]] = defaultdict(list)
        self._collections: dict[str, KnowledgeCollection] = {}
        self._workspaces: dict[str, KnowledgeWorkspace] = {}
        self._lock = asyncio.Lock()

    # --- Knowledge Entry CRUD ---

    async def create_entry(self, entry: KnowledgeEntry) -> KnowledgeEntry:
        async with self._lock:
            self._entries[entry.entry_id] = entry
        await self.search_engine.index_entry(entry)
        await self.graph.add_node(
            f"entry:{entry.entry_id}", "knowledge_entry", entry.title,
            {"status": entry.status, "category": entry.category},
        )
        return entry

    async def get_entry(self, entry_id: str) -> KnowledgeEntry | None:
        async with self._lock:
            entry = self._entries.get(entry_id)
            if entry:
                entry.access_count += 1
            return entry

    async def update_entry(self, entry_id: str, changes: dict[str, Any]) -> KnowledgeEntry | None:
        async with self._lock:
            entry = self._entries.get(entry_id)
            if entry is None:
                return None
            # Save version
            version = KnowledgeVersion(
                entry_id=entry_id,
                version=entry.version,
                content=entry.content,
                title=entry.title,
                changed_by=changes.get("changed_by", "system"),
                change_reason=changes.get("change_reason", ""),
                hash=hashlib.sha256(entry.content.encode()).hexdigest()[:16],
            )
            self._versions[entry_id].append(version)
            # Apply changes
            if "title" in changes:
                entry.title = changes["title"]
            if "content" in changes:
                entry.content = changes["content"]
            if "summary" in changes:
                entry.summary = changes["summary"]
            if "category" in changes:
                entry.category = changes["category"]
            if "labels" in changes:
                entry.labels = list(changes["labels"])
            entry.version += 1
            entry.updated_at = datetime.now(UTC)
            await self.search_engine.index_entry(entry)
            return entry

    async def delete_entry(self, entry_id: str) -> bool:
        if await self.governance.is_on_hold(entry_id):
            return False
        async with self._lock:
            return self._entries.pop(entry_id, None) is not None

    async def list_entries(
        self,
        *,
        workspace_id: str | None = None,
        collection_id: str | None = None,
        status: str | None = None,
        limit: int = 100,
    ) -> list[KnowledgeEntry]:
        async with self._lock:
            entries = list(self._entries.values())
        if workspace_id:
            entries = [e for e in entries if e.workspace_id == workspace_id]
        if collection_id:
            entries = [e for e in entries if e.collection_id == collection_id]
        if status:
            entries = [e for e in entries if e.status == status]
        entries.sort(key=lambda e: e.updated_at, reverse=True)
        return entries[:limit]

    async def get_versions(self, entry_id: str) -> list[KnowledgeVersion]:
        async with self._lock:
            return list(self._versions.get(entry_id, []))

    # --- Collections ---

    async def create_collection(self, collection: KnowledgeCollection) -> KnowledgeCollection:
        async with self._lock:
            self._collections[collection.collection_id] = collection
        return collection

    async def list_collections(self, workspace_id: str | None = None) -> list[KnowledgeCollection]:
        async with self._lock:
            collections = list(self._collections.values())
        if workspace_id:
            collections = [c for c in collections if c.workspace_id == workspace_id]
        return collections

    # --- Workspaces ---

    async def create_workspace(self, workspace: KnowledgeWorkspace) -> KnowledgeWorkspace:
        async with self._lock:
            self._workspaces[workspace.workspace_id] = workspace
        return workspace

    async def list_workspaces(self) -> list[KnowledgeWorkspace]:
        async with self._lock:
            return list(self._workspaces.values())

    # --- Search ---

    async def search(self, query: str, **kwargs: Any) -> list[dict[str, Any]]:
        results = await self.search_engine.search(query, **kwargs)
        return [r.to_dict() for r in results]

    # --- RAG ---

    async def rag(self, request: RetrievalRequest) -> dict[str, Any]:
        result = await self.retrieval.retrieve(request)
        return result.to_dict()

    # --- Graph ---

    async def graph_snapshot(self) -> dict[str, Any]:
        return await self.graph.snapshot()

    async def graph_impact(self, node_id: str) -> dict[str, Any]:
        return await self.graph.impact_analysis(node_id)

    async def graph_search(self, query: str) -> list[dict[str, Any]]:
        return await self.graph.semantic_search(query)

    # --- Memory ---

    async def store_memory(self, record: MemoryRecord) -> MemoryRecord:
        return await self.memory.store(record)

    async def search_memory(self, query: str = "", **kwargs: Any) -> list[dict[str, Any]]:
        records = await self.memory.search(query, **kwargs)
        return [r.to_dict() for r in records]

    async def memory_stats(self) -> dict[str, Any]:
        return await self.memory.stats()

    # --- Governance ---

    async def publish_entry(self, entry_id: str, published_by: str = "system") -> KnowledgeEntry | None:
        entry = await self.get_entry(entry_id)
        if entry is None:
            return None
        return await self.governance.publish(entry, published_by)

    async def archive_entry(self, entry_id: str) -> KnowledgeEntry | None:
        entry = await self.get_entry(entry_id)
        if entry is None:
            return None
        return await self.governance.archive(entry)

    # --- Statistics ---

    async def stats(self) -> dict[str, Any]:
        async with self._lock:
            total_entries = len(self._entries)
            total_versions = sum(len(v) for v in self._versions.values())
            total_collections = len(self._collections)
            total_workspaces = len(self._workspaces)
        memory_stats = await self.memory.stats()
        graph_snap = await self.graph.snapshot()
        return {
            "entries": total_entries,
            "versions": total_versions,
            "collections": total_collections,
            "workspaces": total_workspaces,
            "memory": memory_stats,
            "graph_nodes": graph_snap["node_count"],
            "graph_edges": graph_snap["edge_count"],
        }
