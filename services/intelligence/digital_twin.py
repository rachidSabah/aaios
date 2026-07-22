"""Digital Twin — real-time system model + graph visualization.

Creates a live snapshot of the entire AAiOS system as a graph of nodes
(kernel, supervisor, mission_manager, agents, providers, memory, queues,
plugins, MCP, API, dashboard, event_bus) connected by edges representing
data flow and dependencies.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from core.logging import get_logger
from services.intelligence.models import (
    DigitalTwinNode,
    DigitalTwinSnapshot,
    OperationalMetrics,
)

_log = get_logger(__name__)

__all__ = ["DigitalTwinEngine"]


class DigitalTwinEngine:
    """Builds and maintains a digital twin of the AAiOS system.

    The digital twin is a point-in-time snapshot of all system components
    as a graph. It's used for visualization, monitoring, and what-if
    analysis.
    """

    def build_snapshot(
        self,
        metrics: OperationalMetrics,
        *,
        component_health: list[dict[str, Any]] | None = None,
    ) -> DigitalTwinSnapshot:
        """Build a digital twin snapshot from current metrics."""
        nodes: list[DigitalTwinNode] = []
        edges: list[dict[str, str]] = []
        health_map: dict[str, dict[str, Any]] = {}
        if component_health:
            for c in component_health:
                health_map[c["component"]] = c

        def _health(name: str) -> tuple[float, str]:
            h = health_map.get(name, {})
            return h.get("score", 1.0), h.get("status", "healthy")

        # Core kernel
        nodes.append(
            DigitalTwinNode(
                node_id="kernel",
                node_type="kernel",
                name="Kernel",
                status=_health("kernel")[1],
                health_score=_health("kernel")[0],
                properties={
                    "uptime_s": metrics.uptime_s,
                    "throughput_per_s": metrics.event_bus_throughput_per_s,
                },
            )
        )
        # Event bus
        nodes.append(
            DigitalTwinNode(
                node_id="event_bus",
                node_type="event_bus",
                name="Event Bus",
                health_score=1.0,
                properties={"throughput_per_s": metrics.event_bus_throughput_per_s},
            )
        )
        edges.append({"source": "kernel", "target": "event_bus", "type": "publishes_to"})
        # Supervisor
        nodes.append(
            DigitalTwinNode(
                node_id="supervisor",
                node_type="supervisor",
                name="Supervisor",
                status=_health("supervisor")[1],
                health_score=_health("supervisor")[0],
            )
        )
        edges.append({"source": "kernel", "target": "supervisor", "type": "manages"})
        # Mission manager
        nodes.append(
            DigitalTwinNode(
                node_id="mission_manager",
                node_type="mission_manager",
                name="Mission Manager",
                status=_health("mission_manager")[1],
                health_score=_health("mission_manager")[0],
                properties={
                    "active_missions": metrics.active_missions,
                    "total_missions": metrics.total_missions,
                },
            )
        )
        edges.append({"source": "supervisor", "target": "mission_manager", "type": "delegates_to"})
        # Agent registry
        nodes.append(
            DigitalTwinNode(
                node_id="agent_registry",
                node_type="agent_registry",
                name="Agent Registry",
                status=_health("agent_registry")[1],
                health_score=_health("agent_registry")[0],
                properties={
                    "total_agents": metrics.total_agents,
                    "active_agents": metrics.active_agents,
                },
            )
        )
        edges.append({"source": "supervisor", "target": "agent_registry", "type": "dispatches_via"})
        # Model router
        nodes.append(
            DigitalTwinNode(
                node_id="model_router",
                node_type="model_router",
                name="Model Router",
                status=_health("model_router")[1],
                health_score=_health("model_router")[0],
                properties={"avg_reliability": metrics.avg_provider_reliability},
            )
        )
        edges.append({"source": "agent_registry", "target": "model_router", "type": "calls"})
        # Memory
        nodes.append(
            DigitalTwinNode(
                node_id="memory",
                node_type="memory",
                name="Memory Manager",
                status=_health("memory")[1],
                health_score=_health("memory")[0],
                properties={"usage_mb": metrics.memory_usage_mb},
            )
        )
        edges.append({"source": "kernel", "target": "memory", "type": "uses"})
        # Experience store
        nodes.append(
            DigitalTwinNode(
                node_id="experience_store",
                node_type="experience_store",
                name="Experience Store",
                properties={"total_experiences": metrics.total_experiences},
            )
        )
        edges.append({"source": "memory", "target": "experience_store", "type": "indexes"})
        # Task queue
        nodes.append(
            DigitalTwinNode(
                node_id="task_queue",
                node_type="queue",
                name="Task Queue",
                properties={"depth": metrics.queue_depth},
            )
        )
        edges.append({"source": "mission_manager", "target": "task_queue", "type": "submits_to"})
        # Budget
        nodes.append(
            DigitalTwinNode(
                node_id="budget",
                node_type="budget",
                name="Budget",
                status=_health("budget")[1],
                health_score=_health("budget")[0],
                properties={
                    "total_usd": metrics.total_budget_usd,
                    "spent_usd": metrics.total_spent_usd,
                    "utilization_pct": (
                        metrics.total_spent_usd / max(1, metrics.total_budget_usd) * 100
                    )
                    if metrics.total_budget_usd > 0
                    else 0,
                },
            )
        )
        edges.append({"source": "mission_manager", "target": "budget", "type": "tracks"})
        # API
        nodes.append(
            DigitalTwinNode(
                node_id="api",
                node_type="api",
                name="REST API",
                properties={"routes": 73},
            )
        )
        edges.append({"source": "api", "target": "mission_manager", "type": "exposes"})
        # Dashboard
        nodes.append(
            DigitalTwinNode(
                node_id="dashboard",
                node_type="dashboard",
                name="Dashboard",
            )
        )
        edges.append({"source": "dashboard", "target": "api", "type": "calls"})

        # Compute overall health
        scores = [n.health_score for n in nodes if n.health_score > 0]
        overall = sum(scores) / len(scores) if scores else 1.0

        return DigitalTwinSnapshot(
            timestamp=datetime.now(UTC),
            nodes=nodes,
            edges=edges,
            overall_health=overall,
        )
