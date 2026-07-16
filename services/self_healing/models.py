"""Self-healing models — Pydantic models for the self-healing subsystem."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class HealingTrigger(StrEnum):
    """Failure types that can trigger self-healing."""

    MISSING_DEPENDENCY = "missing_dependency"
    BROKEN_CONFIGURATION = "broken_configuration"
    MISSING_PLUGIN = "missing_plugin"
    PROVIDER_FAILURE = "provider_failure"
    DATABASE_CORRUPTION = "database_corruption"
    BROKEN_MIGRATIONS = "broken_migrations"
    PERMISSION_ISSUES = "permission_issues"
    PORT_CONFLICTS = "port_conflicts"
    CORRUPTED_CACHE = "corrupted_cache"
    EXPIRED_SECRETS = "expired_secrets"
    EXPIRED_CERTIFICATES = "expired_certificates"
    INVALID_API_KEYS = "invalid_api_keys"
    BROKEN_WORKSPACE = "broken_workspace"
    BROKEN_SYMBOLIC_LINKS = "broken_symbolic_links"
    CORRUPTED_INDEXES = "corrupted_indexes"
    BROKEN_AUDIT_CHAIN = "broken_audit_chain"


class HealingActionType(StrEnum):
    """Automatic repair action types."""

    REPAIR = "repair"
    RESTART = "restart"
    RECONFIGURE = "reconfigure"
    REBIND = "rebind"
    REINSTALL = "reinstall"
    REINDEX = "reindex"
    RECOVER = "recover"
    ROLLBACK = "rollback"
    INVALIDATE_CACHE = "invalidate_cache"
    REBUILD_INDEXES = "rebuild_indexes"
    RETRY = "retry"
    ESCALATE = "escalate"


class HealingStatus(StrEnum):
    """Status of a self-healing operation."""

    DETECTED = "detected"
    WAITING_APPROVAL = "waiting_approval"
    IN_PROGRESS = "in_progress"
    REPAIRED = "repaired"
    FAILED = "failed"
    ESCALATED = "escalated"


class RepairRecord(BaseModel):
    """A log of a single self-healing action."""

    id: str
    trigger: HealingTrigger
    action_type: HealingActionType
    target: str
    status: HealingStatus = HealingStatus.DETECTED
    requires_approval: bool = False
    approved: bool | None = None
    started_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    completed_at: datetime | None = None
    details: str = ""
    error: str | None = None
    backup_path: str | None = None
    audit_hash: str | None = None
