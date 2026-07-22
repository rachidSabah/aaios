"""Node Registry — tracks all nodes (machines) in a distributed AAiOS cluster.

A node is a single AAiOS process running on a machine. The registry tracks:
  - node_id: unique identifier (uuid hex)
  - address: host:port for inter-node communication
  - capabilities: which capability namespaces this node can serve
  - status: online / offline / draining / unhealthy
  - last_heartbeat: timestamp of last heartbeat received
  - load: current CPU/memory/load info
  - tags: user-defined labels for routing (e.g. 'gpu', 'windows', 'linux')

The registry is the source of truth for the cluster topology. The
ClusterManager uses it to dispatch tasks to the right node.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

from core.logging import get_logger

_log = get_logger(__name__)

__all__ = [
    "NodeAlreadyRegisteredError",
    "NodeNotFoundError",
    "NodeRecord",
    "NodeRegistry",
    "NodeStatus",
]


class NodeStatus:
    """Node lifecycle states."""

    ONLINE = "online"
    OFFLINE = "offline"
    DRAINING = "draining"  # not accepting new tasks, finishing existing
    UNHEALTHY = "unhealthy"  # missed heartbeats


class NodeNotFoundError(Exception):
    """Raised when a node ID is not in the registry."""


class NodeAlreadyRegisteredError(Exception):
    """Raised when attempting to register a duplicate node ID or address."""


@dataclass
class NodeRecord:
    """A registered node in the cluster."""

    node_id: str
    address: str  # host:port
    capabilities: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    status: str = NodeStatus.ONLINE
    registered_at: float = field(default_factory=time.time)
    last_heartbeat: float = field(default_factory=time.time)
    load_cpu_percent: float = 0.0
    load_memory_mb: float = 0.0
    load_active_tasks: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "address": self.address,
            "capabilities": list(self.capabilities),
            "tags": list(self.tags),
            "status": self.status,
            "registered_at": self.registered_at,
            "last_heartbeat": self.last_heartbeat,
            "load": {
                "cpu_percent": self.load_cpu_percent,
                "memory_mb": self.load_memory_mb,
                "active_tasks": self.load_active_tasks,
            },
            "metadata": dict(self.metadata),
        }


class NodeRegistry:
    """In-memory node registry with heartbeat expiry.

    The registry runs a background task that periodically marks nodes as
    UNHEALTHY if they miss heartbeats, and OFFLINE if they miss them for
    too long. The check interval and thresholds are configurable.
    """

    def __init__(
        self,
        *,
        heartbeat_timeout_s: float = 30.0,
        offline_timeout_s: float = 90.0,
        check_interval_s: float = 10.0,
    ) -> None:
        self._nodes: dict[str, NodeRecord] = {}
        self._by_address: dict[str, str] = {}  # address -> node_id
        self._lock = asyncio.Lock()
        self._heartbeat_timeout_s = heartbeat_timeout_s
        self._offline_timeout_s = offline_timeout_s
        self._check_interval_s = check_interval_s
        self._check_task: asyncio.Task[None] | None = None
        self._on_node_status_change: Callable[[NodeRecord], Any] | None = None

    def set_status_change_callback(
        self,
        cb: Callable[[NodeRecord], Any],
    ) -> None:
        """Set a callback invoked when a node's status changes."""
        self._on_node_status_change = cb

    async def start(self) -> None:
        """Start the background heartbeat-check task."""
        if self._check_task is None or self._check_task.done():
            self._check_task = asyncio.create_task(self._heartbeat_loop())

    async def stop(self) -> None:
        """Stop the background task."""
        if self._check_task is not None and not self._check_task.done():
            self._check_task.cancel()
            try:
                await self._check_task
            except asyncio.CancelledError:
                pass
            self._check_task = None

    async def _heartbeat_loop(self) -> None:
        """Periodically check for stale heartbeats and update statuses."""
        while True:
            try:
                await asyncio.sleep(self._check_interval_s)
                await self._check_heartbeats()
            except asyncio.CancelledError:
                break
            except Exception as e:
                _log.warning("Heartbeat check loop error: %s", e)

    async def _check_heartbeats(self) -> None:
        """Mark nodes as unhealthy/offline based on last heartbeat."""
        now = time.time()
        async with self._lock:
            for node in self._nodes.values():
                age = now - node.last_heartbeat
                old_status = node.status
                if age > self._offline_timeout_s and node.status != NodeStatus.OFFLINE:
                    node.status = NodeStatus.OFFLINE
                elif age > self._heartbeat_timeout_s and node.status == NodeStatus.ONLINE:
                    node.status = NodeStatus.UNHEALTHY
                if node.status != old_status:
                    _log.info(
                        "Node %s status: %s -> %s (heartbeat age %.1fs)",
                        node.node_id,
                        old_status,
                        node.status,
                        age,
                    )
                    if self._on_node_status_change is not None:
                        try:
                            result = self._on_node_status_change(node)
                            if asyncio.iscoroutine(result):
                                await result
                        except Exception as cb_err:
                            _log.warning("Status change callback failed: %s", cb_err)

    async def register(
        self,
        address: str,
        capabilities: list[str] | None = None,
        tags: list[str] | None = None,
        node_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> NodeRecord:
        """Register a new node."""
        node_id = node_id or uuid4().hex[:16]
        async with self._lock:
            if node_id in self._nodes:
                raise NodeAlreadyRegisteredError(f"Node ID '{node_id}' already registered")
            if address in self._by_address:
                raise NodeAlreadyRegisteredError(
                    f"Address '{address}' already registered to node '{self._by_address[address]}'",
                )
            node = NodeRecord(
                node_id=node_id,
                address=address,
                capabilities=capabilities or [],
                tags=tags or [],
                metadata=metadata or {},
            )
            self._nodes[node_id] = node
            self._by_address[address] = node_id
            _log.info(
                "Registered node '%s' at %s (caps=%s, tags=%s)",
                node_id,
                address,
                node.capabilities,
                node.tags,
            )
            return node

    async def deregister(self, node_id: str) -> bool:
        async with self._lock:
            if node_id not in self._nodes:
                return False
            node = self._nodes[node_id]
            del self._by_address[node.address]
            del self._nodes[node_id]
            _log.info("Deregistered node '%s'", node_id)
            return True

    async def heartbeat(
        self,
        node_id: str,
        *,
        load_cpu_percent: float | None = None,
        load_memory_mb: float | None = None,
        load_active_tasks: int | None = None,
    ) -> NodeRecord:
        """Record a heartbeat from a node."""
        async with self._lock:
            if node_id not in self._nodes:
                raise NodeNotFoundError(f"Node '{node_id}' not registered")
            node = self._nodes[node_id]
            node.last_heartbeat = time.time()
            if node.status == NodeStatus.UNHEALTHY:
                node.status = NodeStatus.ONLINE
                _log.info("Node '%s' recovered — back online", node_id)
            if load_cpu_percent is not None:
                node.load_cpu_percent = load_cpu_percent
            if load_memory_mb is not None:
                node.load_memory_mb = load_memory_mb
            if load_active_tasks is not None:
                node.load_active_tasks = load_active_tasks
            return node

    async def get(self, node_id: str) -> NodeRecord:
        async with self._lock:
            if node_id not in self._nodes:
                raise NodeNotFoundError(f"Node '{node_id}' not registered")
            return self._nodes[node_id]

    async def list_all(self) -> list[NodeRecord]:
        async with self._lock:
            return list(self._nodes.values())

    async def find_by_capability(self, capability: str) -> list[NodeRecord]:
        """Find online nodes that can serve a capability."""
        async with self._lock:
            return [
                n
                for n in self._nodes.values()
                if capability in n.capabilities and n.status == NodeStatus.ONLINE
            ]

    async def find_by_tag(self, tag: str) -> list[NodeRecord]:
        async with self._lock:
            return [n for n in self._nodes.values() if tag in n.tags]

    async def set_status(self, node_id: str, status: str) -> NodeRecord:
        """Manually set a node's status (e.g. mark as draining)."""
        async with self._lock:
            if node_id not in self._nodes:
                raise NodeNotFoundError(f"Node '{node_id}' not registered")
            node = self._nodes[node_id]
            old_status = node.status
            node.status = status
            if old_status != status:
                _log.info(
                    "Node '%s' status manually set: %s -> %s",
                    node_id,
                    old_status,
                    status,
                )
            return node

    async def select_node(
        self,
        capability: str | None = None,
        tags: list[str] | None = None,
        strategy: str = "least_loaded",
    ) -> NodeRecord | None:
        """Select the best node for a task.

        Strategies:
          - least_loaded: fewest active tasks
          - round_robin: rotate through candidates
          - lowest_cpu: lowest CPU usage
        """
        async with self._lock:
            candidates: list[NodeRecord] = []
            for n in self._nodes.values():
                if n.status != NodeStatus.ONLINE:
                    continue
                if capability is not None and capability not in n.capabilities:
                    continue
                if tags is not None and not all(t in n.tags for t in tags):
                    continue
                candidates.append(n)
            if not candidates:
                return None
            if strategy == "least_loaded":
                return min(candidates, key=lambda n: n.load_active_tasks)
            if strategy == "lowest_cpu":
                return min(candidates, key=lambda n: n.load_cpu_percent)
            if strategy == "round_robin":
                # Simple: rotate by index based on time
                idx = int(time.time()) % len(candidates)
                return candidates[idx]
            return candidates[0]
