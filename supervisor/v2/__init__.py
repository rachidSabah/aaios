"""AAiOS v2.0 Supervisor Intelligence — adaptive routing, learning,
persistent planning, multi-agent collaboration, autonomous jobs.
"""

from __future__ import annotations

from supervisor.v2.adaptive_router import AdaptiveRouter, RouterWeights, WeightAdjustment
from supervisor.v2.autonomous_jobs import AutonomousJob, AutonomousJobScheduler, JobStatus
from supervisor.v2.delegation import DelegationManager, DelegationRequest, DelegationResult
from supervisor.v2.execution_history import ExecutionHistory, ExecutionOutcome, ExecutionRecord
from supervisor.v2.intelligent_supervisor import IntelligentSupervisor
from supervisor.v2.persistent_planner import PersistentPlanner, RestoredPlan
from supervisor.v2.self_improving import PolicyAdjustment, PolicySuggestion, SelfImprovingPolicy

__all__ = [
    "AdaptiveRouter",
    "AutonomousJob",
    "AutonomousJobScheduler",
    "DelegationManager",
    "DelegationRequest",
    "DelegationResult",
    "ExecutionHistory",
    "ExecutionOutcome",
    "ExecutionRecord",
    "IntelligentSupervisor",
    "JobStatus",
    "PolicyAdjustment",
    "PolicySuggestion",
    "PersistentPlanner",
    "RestoredPlan",
    "RouterWeights",
    "SelfImprovingPolicy",
    "WeightAdjustment",
]
