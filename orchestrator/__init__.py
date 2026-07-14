"""Task Orchestrator — execution infrastructure for plans.

The Orchestrator is the execution infrastructure (L4). It is distinct from
the Supervisor (also L4): the Supervisor makes decisions; the Orchestrator
makes execution reliable. Any L4 caller (Supervisor, Workflow Agent, API)
can submit a plan to the Orchestrator.

Components:
  - ``contracts/`` — Plan, Step, DAG, RetryPolicy, ApprovalGate, Checkpoint,
    ScheduleSpec, BackgroundJob
  - ``core.py`` — TaskOrchestrator (submit, cancel, pause, resume, rollback)
  - ``queue.py`` — PriorityQueue with 5 levels + aging
  - ``dag.py`` — DAG validator + executor (parallel step execution)
  - ``retry.py`` — (in contracts) RetryPolicy with backoff strategies
  - ``checkpoint_store.py`` — InMemoryCheckpointStore
  - ``scheduler.py`` — Scheduler (recurring + delayed tasks)
  - ``workers.py`` — BackgroundWorkerPool
  - ``approval_gates.py`` — ApprovalGateManager (human approval gates)
  - ``workflow_engine.py`` — WorkflowEngine (saved, reusable workflows)
"""

from __future__ import annotations

from orchestrator.approval_gates import (
    ApprovalDecision,
    ApprovalGateManager,
    PendingApproval,
)
from orchestrator.checkpoint_store import InMemoryCheckpointStore
from orchestrator.contracts import (
    ApprovalGate,
    BackgroundJob,
    BackgroundJobResult,
    BackgroundJobStatus,
    BackoffStrategy,
    Checkpoint,
    CheckpointStoreProtocol,
    DAGValidationError,
    GateTimeoutAction,
    GateType,
    Plan,
    PlanStatus,
    RetryPolicy,
    ScheduleSpec,
    ScheduleType,
    Step,
    StepStatus,
    StepType,
)
from orchestrator.core import (
    TaskOrchestrator,
    get_orchestrator,
    init_orchestrator,
    set_orchestrator,
)
from orchestrator.dag import DAGExecutor, DAGValidator, validate_dag
from orchestrator.queue import DEFAULT_CONCURRENCY, Priority, PriorityQueue, QueueItem
from orchestrator.scheduler import ScheduledTask, Scheduler
from orchestrator.workers import BackgroundWorkerPool
from orchestrator.workflow_engine import WorkflowDefinition, WorkflowEngine, WorkflowStore

__all__ = [
    "ApprovalDecision",
    "ApprovalGate",
    "ApprovalGateManager",
    "BackoffStrategy",
    "BackgroundJob",
    "BackgroundJobResult",
    "BackgroundJobStatus",
    "BackgroundWorkerPool",
    "Checkpoint",
    "CheckpointStoreProtocol",
    "DAGExecutor",
    "DAGValidationError",
    "DAGValidator",
    "DEFAULT_CONCURRENCY",
    "GateTimeoutAction",
    "GateType",
    "InMemoryCheckpointStore",
    "PendingApproval",
    "Plan",
    "PlanStatus",
    "Priority",
    "PriorityQueue",
    "QueueItem",
    "RetryPolicy",
    "ScheduleSpec",
    "ScheduleType",
    "ScheduledTask",
    "Scheduler",
    "Step",
    "StepStatus",
    "StepType",
    "TaskOrchestrator",
    "WorkflowDefinition",
    "WorkflowEngine",
    "WorkflowStore",
    "get_orchestrator",
    "init_orchestrator",
    "set_orchestrator",
    "validate_dag",
]
