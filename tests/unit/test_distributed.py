"""Tests for the Distributed Runtime Service."""

from __future__ import annotations

import asyncio

import pytest

from services.distributed import (
    ClusterManager,
    DispatchStatus,
    NodeAlreadyRegisteredError,
    NodeNotFoundError,
    NodeRegistry,
    NodeStatus,
)


@pytest.mark.offline
class TestNodeRegistry:
    """NodeRegistry tests."""

    async def test_register_and_get(self) -> None:
        registry = NodeRegistry()
        node = await registry.register(
            address="10.0.0.1:8000",
            capabilities=["code.generate"],
            tags=["gpu"],
        )
        fetched = await registry.get(node.node_id)
        assert fetched.address == "10.0.0.1:8000"
        assert "code.generate" in fetched.capabilities
        assert "gpu" in fetched.tags
        assert fetched.status == NodeStatus.ONLINE

    async def test_register_duplicate_id(self) -> None:
        registry = NodeRegistry()
        await registry.register(
            address="10.0.0.1:8000",
            node_id="node-1",
        )
        with pytest.raises(NodeAlreadyRegisteredError):
            await registry.register(
                address="10.0.0.2:8000",
                node_id="node-1",
            )

    async def test_register_duplicate_address(self) -> None:
        registry = NodeRegistry()
        await registry.register(address="10.0.0.1:8000", node_id="a")
        with pytest.raises(NodeAlreadyRegisteredError, match="Address"):
            await registry.register(address="10.0.0.1:8000", node_id="b")

    async def test_deregister(self) -> None:
        registry = NodeRegistry()
        node = await registry.register(address="10.0.0.1:8000")
        assert await registry.deregister(node.node_id) is True
        assert await registry.deregister(node.node_id) is False
        with pytest.raises(NodeNotFoundError):
            await registry.get(node.node_id)

    async def test_heartbeat_updates_load(self) -> None:
        registry = NodeRegistry()
        node = await registry.register(address="10.0.0.1:8000")
        updated = await registry.heartbeat(
            node.node_id,
            load_cpu_percent=42.0,
            load_memory_mb=1024.0,
            load_active_tasks=5,
        )
        assert updated.load_cpu_percent == 42.0
        assert updated.load_memory_mb == 1024.0
        assert updated.load_active_tasks == 5

    async def test_list_nodes(self) -> None:
        registry = NodeRegistry()
        await registry.register(address="10.0.0.1:8000", node_id="a")
        await registry.register(address="10.0.0.2:8000", node_id="b")
        nodes = await registry.list_all()
        assert len(nodes) == 2

    async def test_find_by_capability(self) -> None:
        registry = NodeRegistry()
        await registry.register(
            address="10.0.0.1:8000",
            node_id="a",
            capabilities=["code.generate", "code.review"],
        )
        await registry.register(
            address="10.0.0.2:8000",
            node_id="b",
            capabilities=["desktop.screenshot"],
        )
        nodes = await registry.find_by_capability("code.generate")
        assert len(nodes) == 1
        assert nodes[0].node_id == "a"

    async def test_find_by_tag(self) -> None:
        registry = NodeRegistry()
        await registry.register(
            address="10.0.0.1:8000",
            node_id="a",
            tags=["gpu", "windows"],
        )
        await registry.register(
            address="10.0.0.2:8000",
            node_id="b",
            tags=["linux"],
        )
        gpu_nodes = await registry.find_by_tag("gpu")
        assert len(gpu_nodes) == 1
        assert gpu_nodes[0].node_id == "a"

    async def test_set_status(self) -> None:
        registry = NodeRegistry()
        node = await registry.register(address="10.0.0.1:8000")
        updated = await registry.set_status(node.node_id, NodeStatus.DRAINING)
        assert updated.status == NodeStatus.DRAINING

    async def test_select_node_least_loaded(self) -> None:
        registry = NodeRegistry()
        await registry.register(
            address="10.0.0.1:8000",
            node_id="busy",
            capabilities=["code.generate"],
        )
        await registry.heartbeat("busy", load_active_tasks=10)
        await registry.register(
            address="10.0.0.2:8000",
            node_id="idle",
            capabilities=["code.generate"],
        )
        await registry.heartbeat("idle", load_active_tasks=0)
        selected = await registry.select_node(capability="code.generate", strategy="least_loaded")
        assert selected is not None
        assert selected.node_id == "idle"

    async def test_select_node_no_candidates(self) -> None:
        registry = NodeRegistry()
        selected = await registry.select_node(capability="nonexistent")
        assert selected is None

    async def test_select_node_filter_by_tags(self) -> None:
        registry = NodeRegistry()
        await registry.register(
            address="10.0.0.1:8000",
            node_id="a",
            capabilities=["code.generate"],
            tags=["windows"],
        )
        await registry.register(
            address="10.0.0.2:8000",
            node_id="b",
            capabilities=["code.generate"],
            tags=["linux"],
        )
        # Filter by tag
        selected = await registry.select_node(
            capability="code.generate",
            tags=["linux"],
        )
        assert selected is not None
        assert selected.node_id == "b"

    async def test_heartbeat_expiry_marks_unhealthy(self) -> None:
        # Use very short timeouts for testing
        registry = NodeRegistry(
            heartbeat_timeout_s=0.1,
            offline_timeout_s=0.3,
            check_interval_s=0.05,
        )
        node = await registry.register(address="10.0.0.1:8000")
        await registry.start()
        try:
            # Don't send heartbeats — node should become unhealthy
            await asyncio.sleep(0.2)
            fetched = await registry.get(node.node_id)
            assert fetched.status in (NodeStatus.UNHEALTHY, NodeStatus.OFFLINE)
        finally:
            await registry.stop()

    async def test_heartbeat_recovery(self) -> None:
        registry = NodeRegistry(
            heartbeat_timeout_s=0.1,
            offline_timeout_s=0.5,
            check_interval_s=0.05,
        )
        node = await registry.register(address="10.0.0.1:8000")
        await registry.start()
        try:
            # Skip heartbeats to become unhealthy
            await asyncio.sleep(0.2)
            fetched = await registry.get(node.node_id)
            assert fetched.status == NodeStatus.UNHEALTHY
            # Send heartbeat → should recover
            await registry.heartbeat(node.node_id)
            fetched = await registry.get(node.node_id)
            assert fetched.status == NodeStatus.ONLINE
        finally:
            await registry.stop()

    async def test_status_change_callback(self) -> None:
        triggered: list[tuple[str, str]] = []
        registry = NodeRegistry(
            heartbeat_timeout_s=0.1,
            offline_timeout_s=0.3,
            check_interval_s=0.05,
        )

        def cb(node) -> None:
            triggered.append((node.node_id, node.status))

        registry.set_status_change_callback(cb)
        await registry.register(address="10.0.0.1:8000")
        await registry.start()
        try:
            await asyncio.sleep(0.4)
            assert any(s == NodeStatus.UNHEALTHY for _, s in triggered)
        finally:
            await registry.stop()


@pytest.mark.offline
class TestClusterManager:
    """ClusterManager tests."""

    async def test_dispatch_local_execution(self) -> None:
        """Dispatch to a local executor (no remote node needed)."""
        registry = NodeRegistry()
        await registry.register(
            address="127.0.0.1:8000",
            node_id="local",
            capabilities=["code.generate"],
        )

        async def local_executor(capability: str, payload: dict) -> str:
            return f"executed {capability} with {payload.get('input', '')}"

        cluster = ClusterManager(
            registry,
            local_node_id="local",
            local_executor=local_executor,
        )
        handle = await cluster.dispatch(
            capability="code.generate",
            payload={"input": "hello"},
        )
        assert handle.target_node_id == "local"
        result = await cluster.await_result(handle.dispatch_id, timeout_s=5.0)
        assert result.status == DispatchStatus.COMPLETED
        assert "executed code.generate" in str(result.result)

    async def test_dispatch_no_node_available(self) -> None:
        registry = NodeRegistry()
        cluster = ClusterManager(registry, local_node_id="local")
        handle = await cluster.dispatch(
            capability="nonexistent.capability",
            payload={},
        )
        assert handle.status == DispatchStatus.NODE_UNAVAILABLE
        assert handle.error is not None

    async def test_dispatch_failure(self) -> None:
        registry = NodeRegistry()
        await registry.register(
            address="127.0.0.1:8000",
            node_id="local",
            capabilities=["code.generate"],
        )

        async def failing_executor(capability: str, payload: dict) -> str:
            raise RuntimeError("boom")

        cluster = ClusterManager(
            registry,
            local_node_id="local",
            local_executor=failing_executor,
        )
        handle = await cluster.dispatch("code.generate", {})
        result = await cluster.await_result(handle.dispatch_id, timeout_s=5.0)
        assert result.status == DispatchStatus.FAILED
        assert "boom" in (result.error or "")

    async def test_dispatch_timeout(self) -> None:
        registry = NodeRegistry()
        await registry.register(
            address="127.0.0.1:8000",
            node_id="local",
            capabilities=["code.generate"],
        )

        async def slow_executor(capability: str, payload: dict) -> str:
            await asyncio.sleep(10.0)
            return "done"

        cluster = ClusterManager(
            registry,
            local_node_id="local",
            local_executor=slow_executor,
            default_timeout_s=0.1,
        )
        handle = await cluster.dispatch("code.generate", {})
        result = await cluster.await_result(handle.dispatch_id, timeout_s=5.0)
        assert result.status == DispatchStatus.TIMED_OUT

    async def test_cancel_dispatch(self) -> None:
        registry = NodeRegistry()
        await registry.register(
            address="127.0.0.1:8000",
            node_id="local",
            capabilities=["code.generate"],
        )

        async def slow_executor(capability: str, payload: dict) -> str:
            await asyncio.sleep(10.0)
            return "done"

        cluster = ClusterManager(
            registry,
            local_node_id="local",
            local_executor=slow_executor,
            default_timeout_s=10.0,
        )
        handle = await cluster.dispatch("code.generate", {})
        # Cancel immediately
        assert await cluster.cancel(handle.dispatch_id) is True
        # Can't cancel twice
        assert await cluster.cancel(handle.dispatch_id) is False

    async def test_list_dispatches(self) -> None:
        registry = NodeRegistry()
        await registry.register(
            address="127.0.0.1:8000",
            node_id="local",
            capabilities=["code.generate"],
        )

        async def executor(capability: str, payload: dict) -> str:
            return "ok"

        cluster = ClusterManager(
            registry,
            local_node_id="local",
            local_executor=executor,
        )
        await cluster.dispatch("code.generate", {"a": 1})
        await cluster.dispatch("code.generate", {"b": 2})
        dispatches = await cluster.list_dispatches()
        assert len(dispatches) == 2

    async def test_scatter_gather(self) -> None:
        """Scatter N tasks, gather their results."""
        registry = NodeRegistry()
        await registry.register(
            address="127.0.0.1:8000",
            node_id="local",
            capabilities=["code.generate"],
        )

        async def executor(capability: str, payload: dict) -> int:
            await asyncio.sleep(0.05)
            return payload["x"] * 2

        cluster = ClusterManager(
            registry,
            local_node_id="local",
            local_executor=executor,
            default_timeout_s=5.0,
        )
        payloads = [{"x": 1}, {"x": 2}, {"x": 3}, {"x": 4}]
        handles = await cluster.scatter("code.generate", payloads)
        assert len(handles) == 4
        # Wait for all to complete
        results = await cluster.gather([h.dispatch_id for h in handles], timeout_s=5.0)
        assert len(results) == 4
        assert all(r.status == DispatchStatus.COMPLETED for r in results)
        # Verify results (order may vary by completion, but inputs were 1,2,3,4)
        result_values = sorted(int(r.result) for r in results)
        assert result_values == [2, 4, 6, 8]

    async def test_await_unknown_dispatch(self) -> None:
        registry = NodeRegistry()
        cluster = ClusterManager(registry, local_node_id="local")
        result = await cluster.await_result("nonexistent", timeout_s=0.5)
        assert result.status == DispatchStatus.FAILED
        assert "Unknown" in (result.error or "")

    async def test_get_dispatch(self) -> None:
        registry = NodeRegistry()
        await registry.register(
            address="127.0.0.1:8000",
            node_id="local",
            capabilities=["code.generate"],
        )

        async def executor(capability: str, payload: dict) -> str:
            return "ok"

        cluster = ClusterManager(
            registry,
            local_node_id="local",
            local_executor=executor,
        )
        handle = await cluster.dispatch("code.generate", {})
        fetched = await cluster.get_dispatch(handle.dispatch_id)
        assert fetched is not None
        assert fetched.dispatch_id == handle.dispatch_id
        # Wait for completion
        await cluster.await_result(handle.dispatch_id, timeout_s=5.0)
        # Get final state
        fetched = await cluster.get_dispatch(handle.dispatch_id)
        assert fetched is not None
        assert fetched.status in (
            DispatchStatus.COMPLETED,
            DispatchStatus.RUNNING,
        )
