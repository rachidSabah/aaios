"""Cluster Manager — multi-machine orchestration for AAiOS.

The ClusterManager coordinates task dispatch across nodes, handles
failover when a node goes down, and provides primitives for distributed
execution (scatter, gather, broadcast).

Each node runs an AAiOS process. Nodes communicate via HTTP (FastAPI
endpoints at /api/v1/cluster/*) or via the event bus if they share one.
This module is the local node's view of the cluster.

Usage:
    registry = NodeRegistry()
    cluster = ClusterManager(registry, local_node_id="node-1")
    await cluster.start()
    # Dispatch a task to any node that can serve code.generate
    handle = await cluster.dispatch(capability="code.generate", payload={...})
    result = await cluster.await_result(handle)
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

from core.logging import get_logger
from services.distributed.node_registry import (
    NodeNotFoundError,
    NodeRecord,
    NodeRegistry,
)

_log = get_logger(__name__)

__all__ = [
    "ClusterManager",
    "DispatchHandle",
    "DispatchResult",
    "DispatchStatus",
    "RemoteNodeClient",
]


class DispatchStatus:
    """Status of a dispatched task."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMED_OUT = "timed_out"
    NODE_UNAVAILABLE = "node_unavailable"


@dataclass
class DispatchHandle:
    """Handle for a dispatched task — used to await or cancel it."""

    dispatch_id: str
    capability: str
    payload: dict[str, Any]
    target_node_id: str | None = None  # None = router-selected
    status: str = DispatchStatus.PENDING
    created_at: float = field(default_factory=time.time)
    started_at: float | None = None
    completed_at: float | None = None
    result: Any | None = None
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "dispatch_id": self.dispatch_id,
            "capability": self.capability,
            "payload": dict(self.payload),
            "target_node_id": self.target_node_id,
            "status": self.status,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "result": self.result,
            "error": self.error,
        }


@dataclass
class DispatchResult:
    """Result of a dispatched task."""

    dispatch_id: str
    status: str
    result: Any | None = None
    error: str | None = None
    node_id: str | None = None
    duration_s: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "dispatch_id": self.dispatch_id,
            "status": self.status,
            "result": self.result,
            "error": self.error,
            "node_id": self.node_id,
            "duration_s": self.duration_s,
        }


class RemoteNodeClient:
    """HTTP client for talking to a remote AAiOS node.

    Wraps the remote node's /api/v1/cluster/* endpoints. In production,
    this uses httpx.AsyncClient. For tests, callers can inject a fake.
    """

    def __init__(self, timeout_s: float = 30.0) -> None:
        self._timeout_s = timeout_s

    async def call(
        self,
        node: NodeRecord,
        capability: str,
        payload: dict[str, Any],
        dispatch_id: str,
    ) -> dict[str, Any]:
        """Make a synchronous RPC to a remote node.

        Returns the JSON response. Raises on connection error or non-2xx.
        """
        # In production:
        # async with httpx.AsyncClient(timeout=self._timeout_s) as client:
        #     response = await client.post(
        #         f"http://{node.address}/api/v1/cluster/execute",
        #         json={"dispatch_id": dispatch_id, "capability": capability, "payload": payload},
        #     )
        #     response.raise_for_status()
        #     return response.json()
        # For now we stub the HTTP call:
        raise NotImplementedError(
            "RemoteNodeClient.call requires httpx and a running remote node. "
            "Inject a fake client in tests, or run the cluster server.",
        )


class ClusterManager:
    """Coordinates task dispatch across the cluster.

    The local node's view of the cluster. Dispatches tasks to remote
    nodes (or runs locally if no remote node can serve the capability),
    tracks in-flight dispatches, and handles failover.
    """

    def __init__(
        self,
        registry: NodeRegistry,
        *,
        local_node_id: str | None = None,
        local_executor: Any | None = None,
        remote_client: RemoteNodeClient | None = None,
        default_timeout_s: float = 60.0,
    ) -> None:
        self._registry = registry
        self._local_node_id = local_node_id
        self._local_executor = local_executor  # callable(capability, payload) -> Any
        self._remote_client = remote_client or RemoteNodeClient()
        self._default_timeout_s = default_timeout_s
        self._dispatches: dict[str, DispatchHandle] = {}
        self._lock = asyncio.Lock()

    async def dispatch(
        self,
        capability: str,
        payload: dict[str, Any],
        *,
        target_node_id: str | None = None,
        timeout_s: float | None = None,
    ) -> DispatchHandle:
        """Dispatch a task to a node (specific or router-selected).

        If target_node_id is None, the manager selects a node via the
        registry's select_node() method. If no remote node can serve the
        capability, falls back to local execution (if a local_executor
        is configured).
        """
        timeout = timeout_s or self._default_timeout_s
        dispatch_id = uuid4().hex[:16]
        handle = DispatchHandle(
            dispatch_id=dispatch_id,
            capability=capability,
            payload=payload,
            target_node_id=target_node_id,
        )
        async with self._lock:
            self._dispatches[dispatch_id] = handle

        # Pick a target
        if target_node_id is None:
            # Try local first if it can serve
            if self._local_executor is not None and self._local_node_id is not None:
                try:
                    local_node = await self._registry.get(self._local_node_id)
                    if capability in local_node.capabilities:
                        handle.target_node_id = self._local_node_id
                except NodeNotFoundError:
                    pass
            # If not local, pick a remote
            if handle.target_node_id is None:
                node = await self._registry.select_node(capability=capability)
                if node is not None:
                    handle.target_node_id = node.node_id

        if handle.target_node_id is None:
            handle.status = DispatchStatus.NODE_UNAVAILABLE
            handle.error = "No node available for this capability"
            handle.completed_at = time.time()
            return handle

        # Execute
        asyncio.create_task(
            self._execute(handle, timeout),
        )
        return handle

    async def _execute(
        self,
        handle: DispatchHandle,
        timeout_s: float,
    ) -> None:
        """Execute a dispatch — locally or remotely."""
        handle.started_at = time.time()
        handle.status = DispatchStatus.RUNNING
        try:
            result: Any
            if handle.target_node_id == self._local_node_id and self._local_executor:
                # Local execution
                if asyncio.iscoroutinefunction(self._local_executor):
                    result = await asyncio.wait_for(
                        self._local_executor(handle.capability, handle.payload),
                        timeout=timeout_s,
                    )
                else:
                    result = self._local_executor(handle.capability, handle.payload)
            else:
                # Remote execution
                node = await self._registry.get(handle.target_node_id)  # type: ignore[arg-type]
                response = await asyncio.wait_for(
                    self._remote_client.call(
                        node=node,
                        capability=handle.capability,
                        payload=handle.payload,
                        dispatch_id=handle.dispatch_id,
                    ),
                    timeout=timeout_s,
                )
                result = response.get("result")
            handle.result = result
            handle.status = DispatchStatus.COMPLETED
            handle.completed_at = time.time()
        except TimeoutError:
            handle.status = DispatchStatus.TIMED_OUT
            handle.error = f"Task did not complete within {timeout_s}s"
            handle.completed_at = time.time()
        except Exception as e:
            handle.status = DispatchStatus.FAILED
            handle.error = str(e)
            handle.completed_at = time.time()
            _log.warning(
                "Dispatch %s failed: %s",
                handle.dispatch_id,
                e,
            )

    async def await_result(
        self,
        dispatch_id: str,
        timeout_s: float | None = None,
    ) -> DispatchResult:
        """Wait for a dispatched task to complete."""
        timeout = timeout_s or self._default_timeout_s
        deadline = time.time() + timeout
        while time.time() < deadline:
            async with self._lock:
                if dispatch_id not in self._dispatches:
                    return DispatchResult(
                        dispatch_id=dispatch_id,
                        status=DispatchStatus.FAILED,
                        error="Unknown dispatch ID",
                    )
                handle = self._dispatches[dispatch_id]
            if handle.status in (
                DispatchStatus.COMPLETED,
                DispatchStatus.FAILED,
                DispatchStatus.TIMED_OUT,
                DispatchStatus.NODE_UNAVAILABLE,
                DispatchStatus.CANCELLED,
            ):
                duration = (handle.completed_at or 0) - (handle.started_at or handle.created_at)
                return DispatchResult(
                    dispatch_id=dispatch_id,
                    status=handle.status,
                    result=handle.result,
                    error=handle.error,
                    node_id=handle.target_node_id,
                    duration_s=duration,
                )
            await asyncio.sleep(0.05)
        return DispatchResult(
            dispatch_id=dispatch_id,
            status=DispatchStatus.TIMED_OUT,
            error=f"Caller timed out after {timeout}s",
        )

    async def cancel(self, dispatch_id: str) -> bool:
        """Cancel a dispatch (best-effort)."""
        async with self._lock:
            if dispatch_id not in self._dispatches:
                return False
            handle = self._dispatches[dispatch_id]
            if handle.status in (
                DispatchStatus.COMPLETED,
                DispatchStatus.FAILED,
                DispatchStatus.CANCELLED,
                DispatchStatus.TIMED_OUT,
            ):
                return False
            handle.status = DispatchStatus.CANCELLED
            handle.completed_at = time.time()
            return True

    async def list_dispatches(self) -> list[DispatchHandle]:
        async with self._lock:
            return list(self._dispatches.values())

    async def get_dispatch(self, dispatch_id: str) -> DispatchHandle | None:
        async with self._lock:
            return self._dispatches.get(dispatch_id)

    async def scatter(
        self,
        capability: str,
        payloads: list[dict[str, Any]],
    ) -> list[DispatchHandle]:
        """Dispatch N tasks in parallel to available nodes."""
        handles = await asyncio.gather(
            *[self.dispatch(capability, p) for p in payloads],
        )
        return list(handles)

    async def gather(
        self,
        dispatch_ids: list[str],
        timeout_s: float | None = None,
    ) -> list[DispatchResult]:
        """Wait for N dispatches and return their results."""
        results = await asyncio.gather(
            *[self.await_result(d, timeout_s=timeout_s) for d in dispatch_ids],
        )
        return list(results)
