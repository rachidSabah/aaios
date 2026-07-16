"""Execution models — requests, results, policies, approvals, audit entries.

An ExecutionRequest represents a unit of real-world work: a command to run,
a file to write, a git operation, a browser action, etc. Every request
passes through the Policy Engine, Approval Engine, Sandbox, and Audit
Recorder before, during, and after execution.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any
from uuid import uuid4

__all__ = [
    "ApprovalRequest",
    "ApprovalStatus",
    "AuditEntry",
    "ExecutionDomain",
    "ExecutionLog",
    "ExecutionPolicy",
    "ExecutionRequest",
    "ExecutionResult",
    "ExecutionStatus",
    "ExecutionStep",
    "LogLevel",
    "ResourceUsage",
    "RollbackPlan",
    "SandboxConfig",
]


class ExecutionStatus(StrEnum):
    """Execution lifecycle states."""

    PENDING = "pending"
    APPROVING = "approving"
    APPROVED = "approved"
    REJECTED = "rejected"
    QUEUED = "queued"
    DISPATCHED = "dispatched"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"
    ROLLED_BACK = "rolled_back"


class ExecutionDomain(StrEnum):
    """Execution domains — categories of real-world operations."""

    DESKTOP = "desktop"
    BROWSER = "browser"
    FILESYSTEM = "filesystem"
    TERMINAL = "terminal"
    GIT = "git"
    DOCKER = "docker"
    KUBERNETES = "kubernetes"
    SSH = "ssh"
    DATABASE = "database"
    REST_API = "rest_api"
    CLOUD = "cloud"
    CI_CD = "ci_cd"
    DOCUMENT = "document"
    SPREADSHEET = "spreadsheet"
    EMAIL = "email"
    CALENDAR = "calendar"
    COMMUNICATION = "communication"


class ApprovalStatus(StrEnum):
    """Approval gate status."""

    NOT_REQUIRED = "not_required"
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"


class LogLevel(StrEnum):
    """Log levels for execution output."""

    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class ExecutionPolicy:
    """Policy governing an execution request.

    Defines permissions, rate limits, timeout, sandbox constraints,
    and whether approval is required.
    """

    allowed_domains: list[str] = field(default_factory=lambda: [d.value for d in ExecutionDomain])
    denied_domains: list[str] = field(default_factory=list)
    requires_approval: bool = False
    approval_timeout_s: float = 300.0
    max_timeout_s: float = 300.0
    max_retries: int = 2
    rate_limit_per_minute: int = 60
    sandbox_enabled: bool = True
    sandbox_config: SandboxConfig = field(default_factory=lambda: SandboxConfig())
    allowed_paths: list[str] = field(default_factory=list)
    denied_paths: list[str] = field(default_factory=lambda: ["/etc", "/root", "/var/log"])
    allowed_hosts: list[str] = field(default_factory=list)  # empty = all
    denied_hosts: list[str] = field(default_factory=list)
    rollback_enabled: bool = True
    audit_enabled: bool = True
    max_memory_mb: int = 1024
    max_cpu_percent: float = 80.0
    max_disk_mb: int = 1024
    max_network_bytes: int = 100 * 1024 * 1024  # 100MB

    def is_domain_allowed(self, domain: str) -> bool:
        """Check if a domain is allowed by this policy."""
        if domain in self.denied_domains:
            return False
        return domain in self.allowed_domains

    def is_path_allowed(self, path: str) -> bool:
        """Check if a filesystem path is allowed."""
        for denied in self.denied_paths:
            if path.startswith(denied):
                return False
        if not self.allowed_paths:
            return True
        return any(path.startswith(allowed) for allowed in self.allowed_paths)

    def is_host_allowed(self, host: str) -> bool:
        """Check if a network host is allowed."""
        if host in self.denied_hosts:
            return False
        if not self.allowed_hosts:
            return True
        return host in self.allowed_hosts

    def to_dict(self) -> dict[str, Any]:
        return {
            "allowed_domains": list(self.allowed_domains),
            "denied_domains": list(self.denied_domains),
            "requires_approval": self.requires_approval,
            "approval_timeout_s": self.approval_timeout_s,
            "max_timeout_s": self.max_timeout_s,
            "max_retries": self.max_retries,
            "rate_limit_per_minute": self.rate_limit_per_minute,
            "sandbox_enabled": self.sandbox_enabled,
            "sandbox_config": self.sandbox_config.to_dict(),
            "allowed_paths": list(self.allowed_paths),
            "denied_paths": list(self.denied_paths),
            "allowed_hosts": list(self.allowed_hosts),
            "denied_hosts": list(self.denied_hosts),
            "rollback_enabled": self.rollback_enabled,
            "audit_enabled": self.audit_enabled,
            "max_memory_mb": self.max_memory_mb,
            "max_cpu_percent": self.max_cpu_percent,
            "max_disk_mb": self.max_disk_mb,
            "max_network_bytes": self.max_network_bytes,
        }


@dataclass
class SandboxConfig:
    """Configuration for the execution sandbox."""

    enabled: bool = True
    working_dir: str = "/tmp/aaios/sandbox"
    env_vars: dict[str, str] = field(default_factory=dict)
    isolated_network: bool = False
    isolated_filesystem: bool = False
    temp_dir: str = "/tmp/aaios/sandbox/tmp"
    log_dir: str = "/tmp/aaios/sandbox/logs"

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "working_dir": self.working_dir,
            "env_vars": dict(self.env_vars),
            "isolated_network": self.isolated_network,
            "isolated_filesystem": self.isolated_filesystem,
            "temp_dir": self.temp_dir,
            "log_dir": self.log_dir,
        }


@dataclass
class ResourceUsage:
    """Resource usage during execution."""

    cpu_seconds: float = 0.0
    memory_peak_mb: float = 0.0
    disk_mb: float = 0.0
    network_bytes_in: int = 0
    network_bytes_out: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "cpu_seconds": round(self.cpu_seconds, 4),
            "memory_peak_mb": round(self.memory_peak_mb, 2),
            "disk_mb": round(self.disk_mb, 2),
            "network_bytes_in": self.network_bytes_in,
            "network_bytes_out": self.network_bytes_out,
        }


@dataclass
class ExecutionLog:
    """A single log entry from an execution."""

    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    level: str = LogLevel.INFO.value
    message: str = ""
    source: str = ""  # stdout, stderr, system

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp.isoformat(),
            "level": self.level,
            "message": self.message,
            "source": self.source,
        }


@dataclass
class RollbackPlan:
    """A plan for rolling back an execution.

    Contains the steps needed to undo the execution's effects.
    """

    plan_id: str = field(default_factory=lambda: uuid4().hex[:12])
    steps: list[dict[str, Any]] = field(default_factory=list)
    can_rollback: bool = True
    rollback_reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "steps": list(self.steps),
            "can_rollback": self.can_rollback,
            "rollback_reason": self.rollback_reason,
        }


@dataclass
class ExecutionStep:
    """A single step in a multi-step execution."""

    step_id: str = field(default_factory=lambda: uuid4().hex[:8])
    name: str = ""
    action: str = ""
    parameters: dict[str, Any] = field(default_factory=dict)
    status: str = "pending"
    output: str = ""
    error: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "step_id": self.step_id,
            "name": self.name,
            "action": self.action,
            "parameters": dict(self.parameters),
            "status": self.status,
            "output": self.output,
            "error": self.error,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }


@dataclass
class ApprovalRequest:
    """An approval request for a sensitive execution."""

    approval_id: str = field(default_factory=lambda: uuid4().hex[:12])
    execution_id: str = ""
    domain: str = ""
    action: str = ""
    description: str = ""
    risk_level: str = "medium"  # low, medium, high, critical
    requested_by: str = "system"
    requested_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    decided_at: datetime | None = None
    decided_by: str | None = None
    status: str = ApprovalStatus.PENDING.value
    decision_reason: str = ""
    expires_at: datetime = field(default_factory=lambda: datetime.now(UTC) + timedelta(minutes=5))

    def is_expired(self) -> bool:
        return datetime.now(UTC) > self.expires_at

    def to_dict(self) -> dict[str, Any]:
        return {
            "approval_id": self.approval_id,
            "execution_id": self.execution_id,
            "domain": self.domain,
            "action": self.action,
            "description": self.description,
            "risk_level": self.risk_level,
            "requested_by": self.requested_by,
            "requested_at": self.requested_at.isoformat(),
            "decided_at": self.decided_at.isoformat() if self.decided_at else None,
            "decided_by": self.decided_by,
            "status": self.status,
            "decision_reason": self.decision_reason,
            "expires_at": self.expires_at.isoformat(),
            "is_expired": self.is_expired(),
        }


@dataclass
class AuditEntry:
    """An immutable audit log entry for an execution.

    Records WHO did WHAT, WHERE, WHEN, WHY, and the outcome. Every
    execution generates at least 3 audit entries: request, dispatch,
    and completion.
    """

    audit_id: str = field(default_factory=lambda: uuid4().hex[:12])
    execution_id: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    event: str = ""  # requested, approved, rejected, dispatched, started, completed, failed, cancelled, rolled_back
    actor: str = "system"
    domain: str = ""
    action: str = ""
    target: str = ""
    outcome: str = ""  # success, failure, pending
    details: dict[str, Any] = field(default_factory=dict)
    risk_level: str = "low"

    def to_dict(self) -> dict[str, Any]:
        return {
            "audit_id": self.audit_id,
            "execution_id": self.execution_id,
            "timestamp": self.timestamp.isoformat(),
            "event": self.event,
            "actor": self.actor,
            "domain": self.domain,
            "action": self.action,
            "target": self.target,
            "outcome": self.outcome,
            "details": dict(self.details),
            "risk_level": self.risk_level,
        }


@dataclass
class ExecutionRequest:
    """A request to execute real-world work.

    Contains the domain (what type of operation), action (specific operation),
    parameters (operation-specific inputs), and policy constraints.
    """

    execution_id: str = field(default_factory=lambda: uuid4().hex[:16])
    domain: str = ExecutionDomain.TERMINAL.value
    action: str = ""  # e.g. "run_command", "write_file", "git_clone"
    parameters: dict[str, Any] = field(default_factory=dict)
    description: str = ""
    requested_by: str = "system"
    mission_id: str | None = None
    wbs_node_id: str | None = None
    priority: str = "normal"  # critical, high, normal, low, background
    policy: ExecutionPolicy = field(default_factory=ExecutionPolicy)
    timeout_s: float = 120.0
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    status: str = ExecutionStatus.PENDING.value
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "execution_id": self.execution_id,
            "domain": self.domain,
            "action": self.action,
            "parameters": dict(self.parameters),
            "description": self.description,
            "requested_by": self.requested_by,
            "mission_id": self.mission_id,
            "wbs_node_id": self.wbs_node_id,
            "priority": self.priority,
            "policy": self.policy.to_dict(),
            "timeout_s": self.timeout_s,
            "created_at": self.created_at.isoformat(),
            "status": self.status,
            "tags": list(self.tags),
            "metadata": dict(self.metadata),
        }


@dataclass
class ExecutionResult:
    """The result of an execution."""

    execution_id: str = ""
    status: str = ExecutionStatus.PENDING.value
    exit_code: int | None = None
    stdout: str = ""
    stderr: str = ""
    output: Any = None
    error: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    duration_s: float = 0.0
    retries: int = 0
    resource_usage: ResourceUsage = field(default_factory=ResourceUsage)
    logs: list[ExecutionLog] = field(default_factory=list)
    artifacts: list[dict[str, Any]] = field(default_factory=list)
    rollback_plan: RollbackPlan | None = None
    steps: list[ExecutionStep] = field(default_factory=list)
    approval_id: str | None = None

    @property
    def succeeded(self) -> bool:
        return self.status == ExecutionStatus.SUCCEEDED.value

    def to_dict(self) -> dict[str, Any]:
        return {
            "execution_id": self.execution_id,
            "status": self.status,
            "exit_code": self.exit_code,
            "stdout": self.stdout[:10000],  # truncate for API
            "stderr": self.stderr[:10000],
            "output": self.output,
            "error": self.error,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "duration_s": round(self.duration_s, 4),
            "retries": self.retries,
            "resource_usage": self.resource_usage.to_dict(),
            "logs": [log.to_dict() for log in self.logs],
            "artifacts": list(self.artifacts),
            "rollback_plan": self.rollback_plan.to_dict() if self.rollback_plan else None,
            "steps": [s.to_dict() for s in self.steps],
            "approval_id": self.approval_id,
            "succeeded": self.succeeded,
        }
