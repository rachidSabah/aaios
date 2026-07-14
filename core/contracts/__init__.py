"""Pydantic v2 models and Python Protocols shared across the entire system.

This package is the canonical source of typed contracts. Anything crossing
a module boundary must use a model from here (INV-03). No bare dicts.

Layering rule (INV-01): contracts are L1 (kernel). They may not import from
L2 (services), L3 (agents), L4 (supervisor), or L5 (surfaces).
"""

from __future__ import annotations

from core.contracts.actor import ActorRef, ActorType
from core.contracts.event import Event, EventEnvelope, EventTopic
from core.contracts.health import HealthReport, HealthState
from core.contracts.permission import (
    Permission,
    PermissionDecision,
    PermissionRequest,
)
from core.contracts.task import (
    TaskContext,
    TaskId,
    TaskProgress,
    TaskProgressKind,
    TaskRequest,
    TaskResult,
    TaskResultStatus,
    TaskStatus,
)
from core.contracts.timestamp import utc_now

__all__ = [
    "ActorRef",
    "ActorType",
    "Event",
    "EventEnvelope",
    "EventTopic",
    "HealthReport",
    "HealthState",
    "Permission",
    "PermissionDecision",
    "PermissionRequest",
    "TaskContext",
    "TaskId",
    "TaskProgress",
    "TaskProgressKind",
    "TaskRequest",
    "TaskResult",
    "TaskResultStatus",
    "TaskStatus",
    "utc_now",
]
