"""AAiOS v3.0 — Autonomous Mission & Organization System.

A new organizational layer above the existing Supervisor. Transforms
AAiOS from an Agent Runtime into an Autonomous AI Organization capable
of executing complex, long-running missions consisting of thousands of
coordinated tasks executed by hundreds of specialized agents under
executive supervision.

Components:
  - models: Mission, WBSNode, Decision, Risk, Milestone, ApprovalGate,
    Budget, QualityMetrics, ResourceAllocation, MissionArtifact
  - state_machine: MissionStateMachine with 8 states + legal transitions
  - store: MissionStore (JSON persistence, in-memory indices)
  - wbs_engine: WorkBreakdownEngine (decompose goals → WBS DAG)
  - decision_engine: ExecutiveDecisionEngine (evidence-based decisions)
  - collaboration: CollaborationEngine (negotiation, voting, peer review)
  - resource_manager: ResourceManager (agent/provider/budget allocation)
  - persistence: MissionPersistence + MissionRecovery + MissionReplay + MissionHistory
  - analytics: MissionAnalytics + MissionSearcher + MissionExporter
  - manager: MissionManager (top-level facade)

Integration (backward-compatible):
  - Sits above the existing Supervisor (Layer 0 above runtime)
  - Uses the existing event bus for mission events
  - No changes to existing runtime — pure extension
"""

from __future__ import annotations

from services.organization.analytics import (
    MissionAnalytics,
    MissionExporter,
    MissionSearcher,
    MissionSearchResult,
    PortfolioMetrics,
    TimelineEntry,
)
from services.organization.collaboration import (
    AgentMessage,
    CollaborationEngine,
    ConflictResolution,
    ConsensusResult,
    DelegationRequest,
    DelegationResult,
    NegotiationResult,
    PeerReview,
    ReviewVerdict,
    Vote,
    VotingResult,
)
from services.organization.decision_engine import (
    DecisionContext,
    DecisionEngine,
    DecisionEvidence,
    DecisionRecommendation,
)
from services.organization.manager import (
    IllegalTransitionError,
    MissionFilter,
    MissionManager,
    MissionNotFoundError,
    MissionPriority,
    MissionStatus,
    MissionSummary,
    ReplayResult,
    WBSType,
)
from services.organization.models import (
    ApprovalGate,
    ApprovalStatus,
    Budget,
    Decision,
    DecisionType,
    ExecutiveRole,
    Milestone,
    Mission,
    MissionArtifact,
    MissionMetrics,
    QualityMetrics,
    ResourceAllocation,
    Risk,
    RiskSeverity,
    WBSNode,
)
from services.organization.persistence import (
    HistoryEntry,
    MissionHistory,
    MissionPersistence,
    MissionRecovery,
    MissionReplay,
)
from services.organization.resource_manager import (
    AgentAssignment,
    ProviderAssignment,
    ResourceManager,
    ResourcePool,
    ResourceUtilization,
)
from services.organization.state_machine import (
    TRANSITION_EVENTS,
    MissionStateMachine,
    MissionStateTransition,
)
from services.organization.store import MissionStore
from services.organization.wbs_engine import WorkBreakdownEngine

__all__ = [
    "AgentAssignment",
    "AgentMessage",
    "ApprovalGate",
    "ApprovalStatus",
    "Budget",
    "CollaborationEngine",
    "ConflictResolution",
    "ConsensusResult",
    "Decision",
    "DecisionContext",
    "DecisionEngine",
    "DecisionEvidence",
    "DecisionRecommendation",
    "DecisionType",
    "DelegationRequest",
    "DelegationResult",
    "ExecutiveRole",
    "HistoryEntry",
    "IllegalTransitionError",
    "Mission",
    "MissionAnalytics",
    "MissionArtifact",
    "MissionExporter",
    "MissionFilter",
    "MissionHistory",
    "MissionManager",
    "MissionMetrics",
    "MissionNotFoundError",
    "MissionPersistence",
    "MissionPriority",
    "MissionRecovery",
    "MissionReplay",
    "MissionSearchResult",
    "MissionSearcher",
    "MissionStateMachine",
    "MissionStateTransition",
    "MissionStatus",
    "MissionStore",
    "MissionSummary",
    "Milestone",
    "NegotiationResult",
    "PeerReview",
    "PortfolioMetrics",
    "ProviderAssignment",
    "QualityMetrics",
    "ReplayResult",
    "ResourceAllocation",
    "ResourceManager",
    "ResourcePool",
    "ResourceUtilization",
    "ReviewVerdict",
    "Risk",
    "RiskSeverity",
    "TimelineEntry",
    "TRANSITION_EVENTS",
    "Vote",
    "VotingResult",
    "WBSNode",
    "WBSType",
    "WorkBreakdownEngine",
]
