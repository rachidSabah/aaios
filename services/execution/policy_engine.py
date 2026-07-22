"""Execution Policy Engine + Approval Engine + Sandbox.

PolicyEngine: validates requests against RBAC rules, rate limits, path/host
restrictions, and domain allowlists. Returns a policy decision (allow/deny/
requires_approval) with reasoning.

ApprovalEngine: manages approval gates for sensitive operations. Tracks
pending approvals, enforces timeouts, and records decisions.

Sandbox: provides isolated execution environment with working directory,
resource limits, and cleanup.
"""

from __future__ import annotations

import asyncio
import os
import shutil
import tempfile
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from core.logging import get_logger
from services.execution.models import (
    ApprovalRequest,
    ApprovalStatus,
    ExecutionDomain,
    ExecutionPolicy,
    ExecutionRequest,
    SandboxConfig,
)

_log = get_logger(__name__)

__all__ = [
    "ApprovalEngine",
    "PolicyDecision",
    "PolicyEngine",
    "RateLimitExceededError",
    "Sandbox",
]


@dataclass
class PolicyDecision:
    """The result of policy evaluation."""

    allowed: bool
    requires_approval: bool
    risk_level: str = "low"
    reason: str = ""
    policy: ExecutionPolicy | None = None
    violations: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "allowed": self.allowed,
            "requires_approval": self.requires_approval,
            "risk_level": self.risk_level,
            "reason": self.reason,
            "violations": list(self.violations),
        }


class RateLimitExceededError(Exception):
    """Raised when rate limit is exceeded."""


class PolicyEngine:
    """Validates execution requests against policies.

    Checks:
      1. Domain allowlist/denylist
      2. Path restrictions (for filesystem operations)
      3. Host restrictions (for network operations)
      4. Rate limits (per actor, per domain)
      5. Risk assessment (determines if approval is needed)
    """

    # Actions that always require approval
    HIGH_RISK_ACTIONS: set[str] = {
        "delete_file",
        "delete_directory",
        "format_disk",
        "git_push",
        "git_push_force",
        "git_reset_hard",
        "docker_rm",
        "docker_rmi",
        "docker_system_prune",
        "k8s_delete",
        "k8s_scale_down",
        "db_drop",
        "db_truncate",
        "db_delete",
        "cloud_terminate",
        "cloud_delete",
        "ssh_shutdown",
        "ssh_reboot",
        "email_send_bulk",
    }

    CRITICAL_RISK_ACTIONS: set[str] = {
        "format_disk",
        "git_push_force",
        "git_reset_hard",
        "docker_system_prune",
        "k8s_delete_namespace",
        "db_drop_database",
        "cloud_terminate_instance",
    }

    def __init__(self) -> None:
        self._rate_limits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = asyncio.Lock()

    async def evaluate(
        self,
        request: ExecutionRequest,
        policy: ExecutionPolicy | None = None,
    ) -> PolicyDecision:
        """Evaluate a request against the policy. Returns a decision."""
        pol = policy or request.policy
        violations: list[str] = []

        # 1. Domain check
        if not pol.is_domain_allowed(request.domain):
            violations.append(f"Domain '{request.domain}' is not allowed by policy")

        # 2. Path check (for filesystem operations)
        if request.domain == ExecutionDomain.FILESYSTEM.value:
            path = str(request.parameters.get("path", ""))
            if path and not pol.is_path_allowed(path):
                violations.append(f"Path '{path}' is not allowed by policy")

        # 3. Host check (for network operations)
        if request.domain in (
            ExecutionDomain.SSH.value,
            ExecutionDomain.REST_API.value,
            ExecutionDomain.CLOUD.value,
            ExecutionDomain.DATABASE.value,
        ):
            host = str(request.parameters.get("host", ""))
            if host and not pol.is_host_allowed(host):
                violations.append(f"Host '{host}' is not allowed by policy")

        # 4. Rate limit check
        rate_limit_key = f"{request.requested_by}:{request.domain}"
        if not await self._check_rate_limit(rate_limit_key, pol.rate_limit_per_minute):
            violations.append(
                f"Rate limit exceeded: {pol.rate_limit_per_minute}/min for {rate_limit_key}",
            )

        # 5. Risk assessment
        risk_level = self._assess_risk(request)

        # Determine decision
        if violations:
            return PolicyDecision(
                allowed=False,
                requires_approval=False,
                risk_level=risk_level,
                reason="Policy violations: " + "; ".join(violations),
                policy=pol,
                violations=violations,
            )

        # Check if approval is required
        requires_approval = pol.requires_approval or risk_level in ("high", "critical")
        if request.action in self.HIGH_RISK_ACTIONS:
            requires_approval = True
        if request.action in self.CRITICAL_RISK_ACTIONS:
            requires_approval = True
            risk_level = "critical"

        return PolicyDecision(
            allowed=True,
            requires_approval=requires_approval,
            risk_level=risk_level,
            reason="Approved by policy" if not requires_approval else "Requires approval",
            policy=pol,
        )

    def _assess_risk(self, request: ExecutionRequest) -> str:
        """Assess the risk level of an execution request."""
        if request.action in self.CRITICAL_RISK_ACTIONS:
            return "critical"
        if request.action in self.HIGH_RISK_ACTIONS:
            return "high"
        # Domain-based risk
        high_risk_domains = {
            ExecutionDomain.DOCKER.value,
            ExecutionDomain.KUBERNETES.value,
            ExecutionDomain.CLOUD.value,
            ExecutionDomain.DATABASE.value,
        }
        if request.domain in high_risk_domains:
            return "medium"
        if request.domain in (ExecutionDomain.TERMINAL.value, ExecutionDomain.SSH.value):
            return "medium"
        return "low"

    async def _check_rate_limit(self, key: str, limit: int) -> bool:
        """Check if the rate limit is exceeded. Updates the counter."""
        async with self._lock:
            now = time.time()
            window = 60.0  # 1 minute
            # Remove expired entries
            dq = self._rate_limits[key]
            while dq and dq[0] < now - window:
                dq.popleft()
            if len(dq) >= limit:
                return False
            dq.append(now)
            return True


class ApprovalEngine:
    """Manages approval gates for sensitive executions.

    Tracks pending approvals, enforces timeouts, and records decisions.
    """

    def __init__(self) -> None:
        self._pending: dict[str, ApprovalRequest] = {}
        self._history: list[ApprovalRequest] = []
        self._lock = asyncio.Lock()

    async def request_approval(
        self,
        execution_id: str,
        domain: str,
        action: str,
        description: str,
        risk_level: str = "medium",
        requested_by: str = "system",
        timeout_s: float = 300.0,
    ) -> ApprovalRequest:
        """Create a new approval request."""
        approval = ApprovalRequest(
            execution_id=execution_id,
            domain=domain,
            action=action,
            description=description,
            risk_level=risk_level,
            requested_by=requested_by,
            expires_at=datetime.now(UTC) + timedelta(seconds=timeout_s),
        )
        async with self._lock:
            self._pending[approval.approval_id] = approval
        _log.info(
            "Approval requested: execution=%s domain=%s action=%s risk=%s",
            execution_id,
            domain,
            action,
            risk_level,
        )
        return approval

    async def approve(
        self,
        approval_id: str,
        decided_by: str = "operator",
        reason: str = "",
    ) -> ApprovalRequest | None:
        """Approve a pending request."""
        async with self._lock:
            approval = self._pending.pop(approval_id, None)
            if approval is None:
                return None
            if approval.is_expired():
                approval.status = ApprovalStatus.EXPIRED.value
            else:
                approval.status = ApprovalStatus.APPROVED.value
            approval.decided_at = datetime.now(UTC)
            approval.decided_by = decided_by
            approval.decision_reason = reason
            self._history.append(approval)
            return approval

    async def reject(
        self,
        approval_id: str,
        decided_by: str = "operator",
        reason: str = "",
    ) -> ApprovalRequest | None:
        """Reject a pending request."""
        async with self._lock:
            approval = self._pending.pop(approval_id, None)
            if approval is None:
                return None
            approval.status = ApprovalStatus.REJECTED.value
            approval.decided_at = datetime.now(UTC)
            approval.decided_by = decided_by
            approval.decision_reason = reason
            self._history.append(approval)
            return approval

    async def get_pending(self) -> list[ApprovalRequest]:
        """Get all pending approval requests."""
        async with self._lock:
            # Expire old requests
            expired_ids: list[str] = []
            for aid, approval in self._pending.items():
                if approval.is_expired():
                    approval.status = ApprovalStatus.EXPIRED.value
                    approval.decided_at = datetime.now(UTC)
                    self._history.append(approval)
                    expired_ids.append(aid)
            for aid in expired_ids:
                self._pending.pop(aid, None)
            return list(self._pending.values())

    async def get_by_execution(self, execution_id: str) -> ApprovalRequest | None:
        """Get the approval request for a specific execution."""
        async with self._lock:
            for approval in self._pending.values():
                if approval.execution_id == execution_id:
                    return approval
            # Check history
            for approval in reversed(self._history):
                if approval.execution_id == execution_id:
                    return approval
            return None

    async def get_history(self, limit: int = 100) -> list[ApprovalRequest]:
        """Get approval history."""
        async with self._lock:
            return list(self._history[-limit:])


class Sandbox:
    """Isolated execution environment.

    Creates a temporary working directory, manages environment variables,
    and provides cleanup. In production, this would use containers or
    Job Objects for true isolation.
    """

    def __init__(self, config: SandboxConfig) -> None:
        self._config = config
        self._temp_dirs: list[Path] = []
        self._active = False

    async def setup(self) -> None:
        """Set up the sandbox environment."""
        if not self._config.enabled:
            return
        # Create working directory
        work_dir = Path(self._config.working_dir)
        work_dir.mkdir(parents=True, exist_ok=True)
        # Create temp directory
        temp_dir = Path(self._config.temp_dir)
        temp_dir.mkdir(parents=True, exist_ok=True)
        self._temp_dirs.append(temp_dir)
        # Create log directory
        log_dir = Path(self._config.log_dir)
        log_dir.mkdir(parents=True, exist_ok=True)
        self._active = True
        _log.info("Sandbox setup: working_dir=%s", work_dir)

    async def cleanup(self) -> None:
        """Clean up the sandbox environment."""
        if not self._config.enabled:
            return
        for temp_dir in self._temp_dirs:
            try:
                if temp_dir.exists():
                    shutil.rmtree(temp_dir, ignore_errors=True)
            except Exception as e:
                _log.warning("Sandbox cleanup failed for %s: %s", temp_dir, e)
        self._temp_dirs.clear()
        self._active = False
        _log.info("Sandbox cleaned up")

    @property
    def working_dir(self) -> str:
        return self._config.working_dir

    @property
    def env_vars(self) -> dict[str, str]:
        return dict(self._config.env_vars)

    @property
    def is_active(self) -> bool:
        return self._active

    def create_temp_file(self, suffix: str = "", prefix: str = "aaios_") -> Path:
        """Create a temporary file in the sandbox."""
        fd, path = tempfile.mkstemp(suffix=suffix, prefix=prefix, dir=self._config.temp_dir)
        os.close(fd)
        return Path(path)

    def create_temp_dir(self, prefix: str = "aaios_") -> Path:
        """Create a temporary directory in the sandbox."""
        path = tempfile.mkdtemp(prefix=prefix, dir=self._config.temp_dir)
        return Path(path)
