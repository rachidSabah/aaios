"""AAiOS Dashboard Service — workflow builder backend, live monitoring,
and analytics for the v2.0 dashboard agent.

Components:
  - WorkflowStore: persistent DAG definitions for the visual workflow builder
  - MetricsCollector: event-bus subscriber that records time-series metrics
  - Analytics: high-level aggregations for the analytics page

The dashboard service is the backend that powers the Next.js dashboard's
workflow builder, live monitoring, and analytics pages.
"""

from __future__ import annotations

from services.dashboard.analytics import Analytics
from services.dashboard.metrics_collector import (
    MetricBucket,
    MetricSample,
    MetricsCollector,
    MonitorSnapshot,
)
from services.dashboard.workflow_store import (
    Workflow,
    WorkflowEdge,
    WorkflowNode,
    WorkflowNotFoundError,
    WorkflowStore,
    WorkflowValidationError,
)

__all__ = [
    "Analytics",
    "MetricBucket",
    "MetricSample",
    "MetricsCollector",
    "MonitorSnapshot",
    "Workflow",
    "WorkflowEdge",
    "WorkflowNode",
    "WorkflowNotFoundError",
    "WorkflowStore",
    "WorkflowValidationError",
]
