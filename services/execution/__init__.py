"""AAiOS v4.0 — Autonomous Execution Platform.

A secure autonomous execution platform capable of performing real-world
work across 16 domains: desktop, browser, filesystem, terminal, git,
docker, kubernetes, SSH, database, REST API, cloud, CI/CD, document,
spreadsheet, email, calendar, communication.

Every execution passes through: PolicyEngine → ApprovalEngine → Sandbox →
DomainHandler → Recorder/Audit. All operations are observable, auditable,
permission-controlled, and recoverable.

Components:
  - models: ExecutionRequest, ExecutionResult, ExecutionPolicy, ApprovalRequest,
    AuditEntry, RollbackPlan, SandboxConfig, ResourceUsage, ExecutionLog
  - policy_engine: PolicyEngine (RBAC, rate limits, path/host restrictions),
    ApprovalEngine (approval gates), Sandbox (isolated execution)
  - handlers: 16 domain handlers (filesystem, terminal, git, docker, ssh,
    database, rest_api, browser, desktop, cloud, k8s, ci_cd, document,
    spreadsheet, email, calendar, communication)
  - manager: ExecutionManager facade (queue, dispatch, replay, rollback, audit)

Integration (backward-compatible):
  - Uses existing Gateway for sandboxed subprocess execution
  - Integrates with MissionManager (missions can submit executions)
  - Integrates with IntelligenceEngine (execution metrics feed health scores)
  - Integrates with ExperienceEngine (results recorded as experiences)
  - Uses existing EventBus for audit events
  - No changes to existing runtime — pure extension
"""

from __future__ import annotations

from services.execution.approval_engine import (
    ApprovalRole,
    ProductionApprovalEngine,
    RoleBasedApprovalPolicy,
)
from services.execution.audit_store import (
    AuditQuery,
    AuditRetentionPolicy,
    PersistentAuditStore,
)
from services.execution.handlers import (
    BrowserHandler,
    CalendarHandler,
    CICDHandler,
    CloudHandler,
    CommunicationHandler,
    DatabaseHandler,
    DesktopHandler,
    DockerHandler,
    DocumentHandler,
    DomainHandler,
    EmailHandler,
    FileSystemHandler,
    GitHandler,
    KubernetesHandler,
    RestApiHandler,
    SpreadsheetHandler,
    SSHHandler,
    TerminalHandler,
    get_handler,
)
from services.execution.manager import ExecutionManager, ExecutionNotFoundError
from services.execution.models import (
    ApprovalRequest,
    ApprovalStatus,
    AuditEntry,
    ExecutionDomain,
    ExecutionLog,
    ExecutionPolicy,
    ExecutionRequest,
    ExecutionResult,
    ExecutionStatus,
    ExecutionStep,
    LogLevel,
    ResourceUsage,
    RollbackPlan,
    SandboxConfig,
)
from services.execution.policy_engine import (
    ApprovalEngine,
    PolicyDecision,
    PolicyEngine,
    RateLimitExceededError,
    Sandbox,
)

__all__ = [
    "ApprovalEngine",
    "ApprovalRequest",
    "ApprovalRole",
    "ApprovalStatus",
    "AuditEntry",
    "AuditQuery",
    "AuditRetentionPolicy",
    "BrowserHandler",
    "CICDHandler",
    "CalendarHandler",
    "CloudHandler",
    "CommunicationHandler",
    "DatabaseHandler",
    "DesktopHandler",
    "DockerHandler",
    "DomainHandler",
    "DocumentHandler",
    "EmailHandler",
    "ExecutionDomain",
    "ExecutionLog",
    "ExecutionManager",
    "ExecutionNotFoundError",
    "ExecutionPolicy",
    "ExecutionRequest",
    "ExecutionResult",
    "ExecutionStatus",
    "ExecutionStep",
    "FileSystemHandler",
    "GitHandler",
    "KubernetesHandler",
    "LogLevel",
    "PersistentAuditStore",
    "PolicyDecision",
    "PolicyEngine",
    "ProductionApprovalEngine",
    "RateLimitExceededError",
    "ResourceUsage",
    "RestApiHandler",
    "RoleBasedApprovalPolicy",
    "RollbackPlan",
    "SSHHandler",
    "Sandbox",
    "SandboxConfig",
    "SpreadsheetHandler",
    "TerminalHandler",
    "get_handler",
]
