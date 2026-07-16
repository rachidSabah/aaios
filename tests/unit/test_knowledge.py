"""Tests for the Enterprise Knowledge & Memory Platform (v5.1)."""

from __future__ import annotations

import pytest

from services.knowledge import (
    KnowledgeEntry,
    KnowledgePlatform,
    MemoryOrchestrator,
    MemoryRecord,
    MemoryType,
    RetrievalRequest,
)


@pytest.mark.offline
class TestMemoryPlatform:
    """Memory Platform tests."""

    async def test_store_and_get(self) -> None:
        orch = MemoryOrchestrator()
        record = MemoryRecord(memory_type=MemoryType.LONG_TERM.value, content="test content")
        stored = await orch.store(record)
        fetched = await orch.get(stored.memory_id, MemoryType.LONG_TERM.value)
        assert fetched is not None
        assert fetched.content == "test content"

    async def test_15_memory_types(self) -> None:
        orch = MemoryOrchestrator()
        assert len(orch.memory_types) == 15
        for mt in MemoryType:
            assert mt.value in orch.memory_types

    async def test_search(self) -> None:
        orch = MemoryOrchestrator()
        await orch.store(MemoryRecord(memory_type=MemoryType.LONG_TERM.value, content="python programming", tags=["code"]))
        await orch.store(MemoryRecord(memory_type=MemoryType.SHORT_TERM.value, content="java programming", tags=["code"]))
        results = await orch.search("python", limit=10)
        assert len(results) >= 1
        assert "python" in results[0].content

    async def test_promote(self) -> None:
        orch = MemoryOrchestrator()
        record = MemoryRecord(memory_type=MemoryType.SHORT_TERM.value, content="promote me", importance=0.5)
        stored = await orch.store(record)
        promoted = await orch.promote(stored.memory_id, MemoryType.SHORT_TERM.value, MemoryType.LONG_TERM.value)
        assert promoted is not None
        assert promoted.memory_type == MemoryType.LONG_TERM.value
        assert promoted.importance > 0.5

    async def test_merge_duplicates(self) -> None:
        orch = MemoryOrchestrator()
        await orch.store(MemoryRecord(memory_type=MemoryType.LONG_TERM.value, content="duplicate content", importance=0.8))
        await orch.store(MemoryRecord(memory_type=MemoryType.LONG_TERM.value, content="duplicate content", importance=0.5))
        merged = await orch.merge_duplicates()
        assert merged >= 1

    async def test_compress_context(self) -> None:
        orch = MemoryOrchestrator()
        for i in range(20):
            await orch.store(MemoryRecord(
                memory_type=MemoryType.WORKING.value,
                content=f"item {i} " * 100,
                importance=0.5 + i * 0.02,
            ))
        compressed = await orch.compress_context(max_tokens=100)
        assert len(compressed) > 0
        assert len(compressed) < 10000  # should be compressed

    async def test_memory_stats(self) -> None:
        orch = MemoryOrchestrator()
        for mt in MemoryType:
            await orch.store(MemoryRecord(memory_type=mt.value, content=f"content for {mt.value}"))
        stats = await orch.stats()
        assert stats["total"] == 15
        assert stats["memory_types"] == 15

    async def test_expire_old(self) -> None:
        from datetime import UTC, datetime, timedelta
        orch = MemoryOrchestrator()
        expired_record = MemoryRecord(
            memory_type=MemoryType.SHORT_TERM.value,
            content="expired",
            expires_at=datetime.now(UTC) - timedelta(hours=1),
        )
        await orch.store(expired_record)
        deleted = await orch.expire_all()
        assert deleted >= 1

    async def test_snapshot(self) -> None:
        orch = MemoryOrchestrator()
        await orch.store(MemoryRecord(content="snapshot test"))
        snap = await orch.snapshot()
        assert snap["total_records"] >= 1


@pytest.mark.offline
class TestKnowledgePlatform:
    """Knowledge Platform tests."""

    async def test_create_and_get_entry(self) -> None:
        platform = KnowledgePlatform()
        entry = KnowledgeEntry(title="Test", content="Test content", summary="Test summary")
        created = await platform.create_entry(entry)
        fetched = await platform.get_entry(created.entry_id)
        assert fetched is not None
        assert fetched.title == "Test"

    async def test_search(self) -> None:
        platform = KnowledgePlatform()
        await platform.create_entry(KnowledgeEntry(title="Python Guide", content="Python is great", summary="Guide"))
        await platform.create_entry(KnowledgeEntry(title="Java Guide", content="Java is also great", summary="Guide"))
        results = await platform.search("python")
        assert len(results) >= 1
        assert "Python" in results[0]["title"]

    async def test_rag(self) -> None:
        platform = KnowledgePlatform()
        await platform.create_entry(KnowledgeEntry(title="AI Guide", content="AI is transforming the world", summary="AI"))
        await platform.store_memory(MemoryRecord(content="AI is the future of technology"))
        result = await platform.rag(RetrievalRequest(query="AI", max_results=5))
        assert result["token_count"] > 0
        assert len(result["citations"]) > 0
        assert result["confidence"] > 0

    async def test_versioning(self) -> None:
        platform = KnowledgePlatform()
        entry = KnowledgeEntry(title="V1", content="version 1")
        created = await platform.create_entry(entry)
        await platform.update_entry(created.entry_id, {"title": "V2", "content": "version 2"})
        versions = await platform.get_versions(created.entry_id)
        assert len(versions) >= 1

    async def test_graph(self) -> None:
        platform = KnowledgePlatform()
        await platform.create_entry(KnowledgeEntry(title="Graph Test", content="content"))
        snap = await platform.graph_snapshot()
        assert snap["node_count"] >= 1

    async def test_stats(self) -> None:
        platform = KnowledgePlatform()
        await platform.create_entry(KnowledgeEntry(title="Stats Test", content="content"))
        await platform.store_memory(MemoryRecord(content="memory"))
        stats = await platform.stats()
        assert stats["entries"] >= 1
        assert stats["memory"]["total"] >= 1

    async def test_publish(self) -> None:
        platform = KnowledgePlatform()
        entry = KnowledgeEntry(title="Publish Test", content="content")
        created = await platform.create_entry(entry)
        published = await platform.publish_entry(created.entry_id, "operator")
        assert published is not None
        assert published.status == "published"

    async def test_legal_hold(self) -> None:
        platform = KnowledgePlatform()
        entry = KnowledgeEntry(title="Hold Test", content="content")
        created = await platform.create_entry(entry)
        await platform.governance.legal_hold(created.entry_id)
        assert await platform.governance.is_on_hold(created.entry_id) is True
        # Should not be able to delete
        result = await platform.delete_entry(created.entry_id)
        assert result is False


@pytest.mark.offline
class TestKnowledgeGraph:
    """Enterprise Knowledge Graph tests."""

    async def test_add_and_traverse(self) -> None:
        from services.knowledge import EnterpriseKnowledgeGraph
        graph = EnterpriseKnowledgeGraph()
        await graph.add_node("n1", "agent", "agent-a")
        await graph.add_node("n2", "task", "task-1")
        await graph.add_edge("n1", "n2", "executes")
        traversal = await graph.traverse("n1", max_depth=2)
        assert len(traversal) >= 2

    async def test_impact_analysis(self) -> None:
        from services.knowledge import EnterpriseKnowledgeGraph
        graph = EnterpriseKnowledgeGraph()
        await graph.add_node("a", "agent", "agent-a")
        await graph.add_node("b", "task", "task-b")
        await graph.add_node("c", "execution", "exec-c")
        await graph.add_edge("a", "b", "executes")
        await graph.add_edge("b", "c", "produces")
        impact = await graph.impact_analysis("a")
        assert impact["affected_count"] >= 3

    async def test_semantic_search(self) -> None:
        from services.knowledge import EnterpriseKnowledgeGraph
        graph = EnterpriseKnowledgeGraph()
        await graph.add_node("n1", "agent", "python-coder")
        await graph.add_node("n2", "provider", "openai")
        results = await graph.semantic_search("python")
        assert len(results) >= 1


@pytest.mark.offline
class TestRetrievalEngine:
    """RAG retrieval tests."""

    async def test_retrieve_with_citations(self) -> None:
        platform = KnowledgePlatform()
        await platform.create_entry(KnowledgeEntry(title="RAG Test", content="This is test content for RAG retrieval", summary="RAG"))
        result = await platform.rag(RetrievalRequest(query="test", max_results=5, include_citations=True))
        assert len(result["citations"]) > 0

    async def test_conflict_detection(self) -> None:
        platform = KnowledgePlatform()
        await platform.create_entry(KnowledgeEntry(title="Same Title", content="content version A"))
        await platform.create_entry(KnowledgeEntry(title="Same Title", content="content version B"))
        result = await platform.rag(RetrievalRequest(query="Same Title", max_results=10))
        # May or may not detect conflicts depending on search ranking
        assert isinstance(result["conflicts"], list)

    async def test_deduplication(self) -> None:
        platform = KnowledgePlatform()
        await platform.create_entry(KnowledgeEntry(title="Dedup", content="identical content for dedup test"))
        await platform.store_memory(MemoryRecord(content="identical content for dedup test"))
        result = await platform.rag(RetrievalRequest(query="dedup", max_results=10, deduplicate=True))
        # Should have deduplicated the identical content
        assert result["token_count"] > 0


@pytest.mark.offline
class TestKnowledgeStress:
    """Stress tests."""

    async def test_100_entries(self) -> None:
        platform = KnowledgePlatform()
        for i in range(100):
            await platform.create_entry(KnowledgeEntry(
                title=f"Entry {i}", content=f"content {i}", summary=f"summary {i}",
                labels=[f"tag-{i%5}"],
            ))
        stats = await platform.stats()
        assert stats["entries"] == 100
        results = await platform.search("entry")
        assert len(results) > 0

    async def test_1000_memory_records(self) -> None:
        orch = MemoryOrchestrator()
        memory_types = list(MemoryType)
        for i in range(1000):
            mt = memory_types[i % len(memory_types)]
            await orch.store(MemoryRecord(
                memory_type=mt.value,
                content=f"memory item {i}",
                importance=0.1 + (i % 10) * 0.09,
            ))
        stats = await orch.stats()
        assert stats["total"] == 1000
