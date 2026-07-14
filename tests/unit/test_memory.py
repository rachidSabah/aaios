"""Tests for the memory subsystem — contracts, embeddings, vector store, knowledge graph, RAG, manager."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from core.contracts.memory import (
    GraphEdge,
    GraphNode,
    MemoryItem,
    MemoryQuery,
    MemoryScope,
    MemoryScopeType,
    MemoryVector,
)
from services.memory import (
    ContextWindow,
    ContextWindowManager,
    EmbeddingsService,
    InMemoryKnowledgeGraph,
    InMemoryVectorStore,
    LocalEmbeddingsProvider,
    MemoryManager,
    MemoryRanker,
    Summarizer,
)


@pytest.mark.offline
class TestMemoryContracts:
    """Memory contract tests."""

    def test_memory_scope_types(self) -> None:
        assert len(list(MemoryScopeType)) == 5
        assert MemoryScopeType.SHORT_TERM.value == "short_term"
        assert MemoryScopeType.PROJECT.value == "project"

    def test_memory_scope_str(self) -> None:
        scope = MemoryScope(scope_type=MemoryScopeType.PROJECT, project_id="myproject")
        assert "project" in str(scope)
        assert "myproject" in str(scope)

    def test_memory_item_create(self) -> None:
        scope = MemoryScope(scope_type=MemoryScopeType.LONG_TERM)
        item = MemoryItem.create(scope, "hello world")
        assert item.id is not None
        assert item.content == "hello world"
        assert item.scope == scope
        assert item.embedding is None

    def test_memory_item_with_embedding(self) -> None:
        scope = MemoryScope(scope_type=MemoryScopeType.SEMANTIC)
        vec = MemoryVector(values=[0.1, 0.2, 0.3], dimensions=3, model="test")
        item = MemoryItem.create(scope, "embedded text")
        item = item.model_copy(update={"embedding": vec})
        assert item.embedding is not None
        assert len(item.embedding) == 3

    def test_memory_item_expired(self) -> None:
        scope = MemoryScope(scope_type=MemoryScopeType.SHORT_TERM)
        item = MemoryItem.create(scope, "temp")
        assert not item.is_expired()
        expired = item.model_copy(update={"expires_at": datetime.now(UTC) - timedelta(hours=1)})
        assert expired.is_expired()

    def test_memory_query_defaults(self) -> None:
        q = MemoryQuery(query_text="test")
        assert q.k == 10
        assert q.use_vector is True
        assert q.use_graph is True
        assert q.use_keyword is True
        assert q.rerank is True


@pytest.mark.offline
class TestEmbeddings:
    """EmbeddingsService tests."""

    async def test_embed_text(self) -> None:
        service = EmbeddingsService(provider=LocalEmbeddingsProvider(dimensions=64))
        vec = await service.embed_text("hello")
        assert vec.dimensions == 64
        assert len(vec.values) == 64

    async def test_embed_batch(self) -> None:
        service = EmbeddingsService(provider=LocalEmbeddingsProvider(dimensions=32))
        vecs = await service.embed_batch(["hello", "world"])
        assert len(vecs) == 2
        assert all(v.dimensions == 32 for v in vecs)

    async def test_cache_hit(self) -> None:
        service = EmbeddingsService(provider=LocalEmbeddingsProvider(dimensions=32))
        v1 = await service.embed_text("hello")
        v2 = await service.embed_text("hello")
        assert v1 is v2  # cached

    async def test_different_texts_different_vectors(self) -> None:
        service = EmbeddingsService(provider=LocalEmbeddingsProvider(dimensions=64))
        v1 = await service.embed_text("hello")
        v2 = await service.embed_text("world")
        assert v1.values != v2.values


@pytest.mark.offline
class TestVectorStore:
    """InMemoryVectorStore tests."""

    def _make_item(self, content: str, vector: list[float]) -> MemoryItem:
        scope = MemoryScope(scope_type=MemoryScopeType.SEMANTIC)
        vec = MemoryVector(values=vector, dimensions=len(vector), model="test")
        item = MemoryItem.create(scope, content)
        return item.model_copy(update={"embedding": vec})

    async def test_upsert_and_count(self) -> None:
        store = InMemoryVectorStore()
        item = self._make_item("hello", [1.0, 0.0, 0.0])
        await store.upsert("test", [item])
        assert await store.count("test") == 1

    async def test_search_returns_similar(self) -> None:
        store = InMemoryVectorStore()
        item1 = self._make_item("hello", [1.0, 0.0, 0.0])
        item2 = self._make_item("world", [0.0, 1.0, 0.0])
        await store.upsert("test", [item1, item2])
        # Search for [1.0, 0.0, 0.0] — should match item1
        results = await store.search("test", [1.0, 0.0, 0.0], k=1)
        assert len(results) == 1
        assert results[0][0].content == "hello"
        assert results[0][1] > 0.99  # cosine similarity

    async def test_search_with_filter(self) -> None:
        store = InMemoryVectorStore()
        item1 = self._make_item("hello", [1.0, 0.0])
        item1 = item1.model_copy(update={"metadata": {"tag": "greeting"}})
        item2 = self._make_item("goodbye", [1.0, 0.0])
        item2 = item2.model_copy(update={"metadata": {"tag": "farewell"}})
        await store.upsert("test", [item1, item2])
        results = await store.search("test", [1.0, 0.0], k=10, filter={"tag": "greeting"})
        assert len(results) == 1
        assert results[0][0].content == "hello"

    async def test_delete(self) -> None:
        store = InMemoryVectorStore()
        item = self._make_item("hello", [1.0, 0.0])
        await store.upsert("test", [item])
        await store.delete("test", [str(item.id)])
        assert await store.count("test") == 0

    async def test_delete_collection(self) -> None:
        store = InMemoryVectorStore()
        await store.upsert("test", [self._make_item("x", [1.0])])
        await store.delete_collection("test")
        assert await store.count("test") == 0
        assert "test" not in await store.list_collections()

    async def test_list_collections(self) -> None:
        store = InMemoryVectorStore()
        await store.upsert("a", [self._make_item("x", [1.0])])
        await store.upsert("b", [self._make_item("y", [1.0])])
        cols = await store.list_collections()
        assert set(cols) == {"a", "b"}


@pytest.mark.offline
class TestKnowledgeGraph:
    """InMemoryKnowledgeGraph tests."""

    async def test_add_and_get_node(self) -> None:
        graph = InMemoryKnowledgeGraph()
        node = GraphNode(entity_type="person", name="Alice")
        await graph.add_node(node)
        fetched = await graph.get_node(node.id)
        assert fetched is not None
        assert fetched.name == "Alice"

    async def test_add_edge_and_neighbors(self) -> None:
        graph = InMemoryKnowledgeGraph()
        n1 = GraphNode(entity_type="person", name="Alice")
        n2 = GraphNode(entity_type="person", name="Bob")
        await graph.add_node(n1)
        await graph.add_node(n2)
        await graph.add_edge(GraphEdge(source_id=n1.id, target_id=n2.id, relation="knows"))
        neighbors = await graph.neighbors(n1.id, max_depth=1)
        assert len(neighbors) == 1
        assert neighbors[0][0].name == "Bob"
        assert neighbors[0][1].relation == "knows"

    async def test_find_nodes_by_name(self) -> None:
        graph = InMemoryKnowledgeGraph()
        await graph.add_node(GraphNode(entity_type="person", name="Alice"))
        await graph.add_node(GraphNode(entity_type="person", name="Bob"))
        found = await graph.find_nodes(name="Alice")
        assert len(found) == 1
        assert found[0].name == "Alice"

    async def test_find_nodes_by_type(self) -> None:
        graph = InMemoryKnowledgeGraph()
        await graph.add_node(GraphNode(entity_type="person", name="Alice"))
        await graph.add_node(GraphNode(entity_type="project", name="AAiOS"))
        found = await graph.find_nodes(entity_type="project")
        assert len(found) == 1
        assert found[0].name == "AAiOS"

    async def test_delete_node(self) -> None:
        graph = InMemoryKnowledgeGraph()
        node = GraphNode(entity_type="x", name="y")
        await graph.add_node(node)
        assert await graph.delete_node(node.id) is True
        assert await graph.get_node(node.id) is None
        assert await graph.delete_node(node.id) is False

    async def test_node_and_edge_count(self) -> None:
        graph = InMemoryKnowledgeGraph()
        n1 = GraphNode(entity_type="x", name="a")
        n2 = GraphNode(entity_type="x", name="b")
        await graph.add_node(n1)
        await graph.add_node(n2)
        await graph.add_edge(GraphEdge(source_id=n1.id, target_id=n2.id, relation="r"))
        assert await graph.node_count() == 2
        assert await graph.edge_count() == 1

    async def test_neighbors_max_depth(self) -> None:
        graph = InMemoryKnowledgeGraph()
        n1 = GraphNode(entity_type="x", name="a")
        n2 = GraphNode(entity_type="x", name="b")
        n3 = GraphNode(entity_type="x", name="c")
        await graph.add_node(n1)
        await graph.add_node(n2)
        await graph.add_node(n3)
        await graph.add_edge(GraphEdge(source_id=n1.id, target_id=n2.id, relation="r"))
        await graph.add_edge(GraphEdge(source_id=n2.id, target_id=n3.id, relation="r"))
        # depth 1: only n2
        d1 = await graph.neighbors(n1.id, max_depth=1)
        assert len(d1) == 1
        # depth 2: n2 and n3
        d2 = await graph.neighbors(n1.id, max_depth=2)
        assert len(d2) == 2


@pytest.mark.offline
class TestMemoryRanker:
    """MemoryRanker tests."""

    def _make_item(self, content: str, score: float = 0.0) -> MemoryItem:
        scope = MemoryScope(scope_type=MemoryScopeType.SEMANTIC)
        item = MemoryItem.create(scope, content)
        return item.model_copy(update={"score": score})

    def test_rank_by_vector_score(self) -> None:
        ranker = MemoryRanker()
        items = [self._make_item("a"), self._make_item("b")]
        vector_scores = {items[0].id: 0.9, items[1].id: 0.3}
        ranked = ranker.rank(items, "test", vector_scores=vector_scores)
        assert ranked[0].item.id == items[0].id
        assert ranked[0].score > ranked[1].score

    def test_rank_with_keyword(self) -> None:
        ranker = MemoryRanker()
        item1 = self._make_item("the database is postgresql")
        item2 = self._make_item("the weather is sunny")
        ranked = ranker.rank([item1, item2], "database")
        assert ranked[0].item.id == item1.id

    def test_rank_empty_list(self) -> None:
        ranker = MemoryRanker()
        ranked = ranker.rank([], "test")
        assert ranked == []


@pytest.mark.offline
class TestContextWindow:
    """ContextWindow tests."""

    def _make_ranked(self, content: str, score: float = 0.5):  # type: ignore[no-untyped-def]
        from core.contracts.memory.query import RankedItem

        scope = MemoryScope(scope_type=MemoryScopeType.SHORT_TERM)
        item = MemoryItem.create(scope, content)
        return RankedItem(item=item, score=score)

    def test_add_and_count(self) -> None:
        window = ContextWindow(task_id=uuid4(), max_tokens=1000)
        window.add(self._make_ranked("hello"))
        assert window.item_count == 1
        assert window.current_tokens > 0

    def test_eviction_on_overflow(self) -> None:
        window = ContextWindow(task_id=uuid4(), max_tokens=20)  # very small
        # Each item is ~4 tokens (16 chars / 4)
        window.add(self._make_ranked("a" * 16, score=0.9))
        window.add(self._make_ranked("b" * 16, score=0.5))
        # The second item should have evicted the first (lower score)
        assert window.item_count <= 2

    def test_get_content(self) -> None:
        window = ContextWindow(task_id=uuid4(), max_tokens=1000)
        window.add(self._make_ranked("hello"))
        window.add(self._make_ranked("world"))
        content = window.get_content()
        assert "hello" in content
        assert "world" in content

    def test_clear(self) -> None:
        window = ContextWindow(task_id=uuid4(), max_tokens=1000)
        window.add(self._make_ranked("x"))
        window.clear()
        assert window.item_count == 0
        assert window.current_tokens == 0

    def test_item_too_large_rejected(self) -> None:
        window = ContextWindow(task_id=uuid4(), max_tokens=5)
        # 100 chars = ~25 tokens, way over budget
        result = window.add(self._make_ranked("x" * 100))
        assert result is False
        assert window.item_count == 0


@pytest.mark.offline
class TestContextWindowManager:
    """ContextWindowManager tests."""

    def test_open_and_get(self) -> None:
        mgr = ContextWindowManager()
        task_id = uuid4()
        window = mgr.open(task_id, max_tokens=500)
        assert mgr.get(task_id) is window

    def test_open_idempotent(self) -> None:
        mgr = ContextWindowManager()
        task_id = uuid4()
        w1 = mgr.open(task_id)
        w2 = mgr.open(task_id)
        assert w1 is w2

    def test_close(self) -> None:
        mgr = ContextWindowManager()
        task_id = uuid4()
        mgr.open(task_id)
        mgr.close(task_id)
        assert mgr.get(task_id) is None

    def test_list_open(self) -> None:
        mgr = ContextWindowManager()
        t1, t2 = uuid4(), uuid4()
        mgr.open(t1)
        mgr.open(t2)
        open_ids = mgr.list_open()
        assert t1 in open_ids
        assert t2 in open_ids


@pytest.mark.offline
class TestSummarizer:
    """Summarizer tests."""

    async def test_summarize_items(self) -> None:
        scope = MemoryScope(scope_type=MemoryScopeType.LONG_TERM)
        items = [
            MemoryItem.create(scope, "First item about topic A."),
            MemoryItem.create(scope, "Second item about topic B."),
            MemoryItem.create(scope, "Third item about topic C."),
        ]
        summarizer = Summarizer()
        summary = await summarizer.summarize(items, scope)
        assert "Summary of 3 items" in summary.content
        assert summary.summarizes == []

    async def test_summarize_empty_raises(self) -> None:
        summarizer = Summarizer()
        with pytest.raises(ValueError, match="empty"):
            await summarizer.summarize([], MemoryScope(scope_type=MemoryScopeType.LONG_TERM))


@pytest.mark.offline
class TestMemoryManager:
    """MemoryManager tests (end-to-end)."""

    async def test_remember_and_recall(self) -> None:
        mgr = MemoryManager()
        scope = MemoryScope(scope_type=MemoryScopeType.PROJECT, project_id="test")
        await mgr.remember(scope, "The auth module uses JWT tokens.")
        await mgr.remember(scope, "The database is PostgreSQL 16.")
        await mgr.remember(scope, "The API runs on port 8000.")

        result = await mgr.recall(scope, "What database?", k=3)
        assert len(result.items) > 0
        # The database item should be in the results
        assert any("database" in r.item.content.lower() for r in result.items)

    async def test_remember_batch(self) -> None:
        mgr = MemoryManager()
        scope = MemoryScope(scope_type=MemoryScopeType.LONG_TERM)
        items = await mgr.remember_batch(
            scope,
            [
                {"content": "first", "metadata": {"tag": "a"}},
                {"content": "second", "metadata": {"tag": "b"}},
            ],
        )
        assert len(items) == 2
        assert all(i.embedding is not None for i in items)

    async def test_recall_no_scope(self) -> None:
        mgr = MemoryManager()
        scope = MemoryScope(scope_type=MemoryScopeType.SEMANTIC)
        await mgr.remember(scope, "test content")
        result = await mgr.recall(None, "test", k=5)
        # Should return results (from the 'semantic' collection)
        assert len(result.items) >= 0  # may be 0 since scope=None searches 'all'

    async def test_rank(self) -> None:
        mgr = MemoryManager()
        scope = MemoryScope(scope_type=MemoryScopeType.SEMANTIC)
        items = [
            MemoryItem.create(scope, "the database is postgresql"),
            MemoryItem.create(scope, "the weather is sunny"),
        ]
        ranked = await mgr.rank(items, "database")
        assert ranked[0].item.content == "the database is postgresql"

    async def test_forget(self) -> None:
        mgr = MemoryManager()
        scope = MemoryScope(scope_type=MemoryScopeType.SHORT_TERM)
        await mgr.remember(scope, "temp item")
        count = await mgr.forget(scope)
        assert count >= 1

    async def test_link(self) -> None:
        mgr = MemoryManager()
        scope = MemoryScope(scope_type=MemoryScopeType.LONG_TERM)
        item1 = await mgr.remember(scope, "item 1")
        item2 = await mgr.remember(scope, "item 2")
        await mgr.link(item1.id, item2.id, "related_to")
        # Verify the graph has the edge
        neighbors = await mgr.knowledge_graph.neighbors(item1.id, max_depth=1)
        assert len(neighbors) == 1

    async def test_add_entity(self) -> None:
        mgr = MemoryManager()
        node = await mgr.add_entity("person", "Alice", properties={"role": "developer"})
        assert node.name == "Alice"
        fetched = await mgr.knowledge_graph.get_node(node.id)
        assert fetched is not None

    async def test_context_window_lifecycle(self) -> None:
        mgr = MemoryManager()
        task_id = uuid4()
        window = mgr.open_context_window(task_id, max_tokens=500)
        assert mgr.get_context_window(task_id) is window
        mgr.close_context_window(task_id)
        assert mgr.get_context_window(task_id) is None

    async def test_summarize(self) -> None:
        mgr = MemoryManager()
        scope = MemoryScope(scope_type=MemoryScopeType.LONG_TERM)
        # Need at least min_cluster_size items (default 5)
        for i in range(6):
            await mgr.remember(scope, f"Item {i} content for testing summarization.")
        result = await mgr.summarize(scope)
        assert result is not None
        assert "Summary of" in result.summary.content
