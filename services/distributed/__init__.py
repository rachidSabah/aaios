"""Distributed Runtime Service — multi-machine orchestration for AAiOS.

Components:
  - NodeRegistry: tracks all nodes (machines) in the cluster, with
    heartbeat-based health checking
  - ClusterManager: dispatches tasks to nodes, handles failover, and
    provides scatter/gather primitives for parallel execution

This is the foundation for running AAiOS across multiple machines —
agents can be served by any node that has the right capabilities,
and tasks are routed to the least-loaded node.
"""

from __future__ import annotations

from services.distributed.cluster_manager import (
    ClusterManager,
    DispatchHandle,
    DispatchResult,
    DispatchStatus,
    RemoteNodeClient,
)
from services.distributed.node_registry import (
    NodeAlreadyRegisteredError,
    NodeNotFoundError,
    NodeRecord,
    NodeRegistry,
    NodeStatus,
)

__all__ = [
    "ClusterManager",
    "DispatchHandle",
    "DispatchResult",
    "DispatchStatus",
    "NodeAlreadyRegisteredError",
    "NodeNotFoundError",
    "NodeRecord",
    "NodeRegistry",
    "NodeStatus",
    "RemoteNodeClient",
]
