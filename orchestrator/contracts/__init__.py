"""Orchestrator contracts — Plan, Step, DAG, RetryPolicy, ApprovalGate, Checkpoint.

These are L4 contracts (used by the Task Orchestrator and the Supervisor).
They import from L1 (core.contracts) only — never from L2/L3/L5.
"""

from __future__ import annotations

from orchestrator.contracts.approval_gate import ApprovalGate, GateTimeoutAction, GateType
from orchestrator.contracts.checkpoint import Checkpoint, CheckpointStoreProtocol
from orchestrator.contracts.dag import (
    DAGValidationError,
    Plan,
    PlanStatus,
    Step,
    StepStatus,
    StepType,
)
from orchestrator.contracts.retry import BackoffStrategy, RetryPolicy
from orchestrator.contracts.schedule import ScheduleSpec, ScheduleType
from orchestrator.contracts.work import BackgroundJob, BackgroundJobResult, BackgroundJobStatus

__all__ = [
    "ApprovalGate",
    "BackoffStrategy",
    "BackgroundJob",
    "BackgroundJobResult",
    "BackgroundJobStatus",
    "Checkpoint",
    "CheckpointStoreProtocol",
    "DAGValidationError",
    "GateTimeoutAction",
    "GateType",
    "Plan",
    "PlanStatus",
    "RetryPolicy",
    "ScheduleSpec",
    "ScheduleType",
    "Step",
    "StepStatus",
    "StepType",
]
