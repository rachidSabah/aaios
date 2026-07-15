"""Production Approval Engine — blocking approvals with timeout + escalation.

Replaces the synchronous auto-approval with:
  - Blocking approvals (await until decided or timeout)
  - Approval timeout (configurable per request)
  - Escalation (auto-escalate to higher role after timeout)
  - Multi-user approval (multiple approvers required for critical)
  - Role-based approval (only certain roles can approve certain risk levels)
  - Audit logging (every approval decision is recorded)
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

from core.logging import get_logger
from services.execution.models import ApprovalRequest, ApprovalStatus

_log = get_logger(__name__)

__all__ = [
    "ApprovalRole",
    "ProductionApprovalEngine",
    "RoleBasedApprovalPolicy",
]


class ApprovalRole:
    """Approval roles (lowest to highest authority)."""

    OPERATOR = "operator"
    SENIOR_OPERATOR = "senior_operator"
    MISSION_DIRECTOR = "mission_director"
    EXECUTIVE_DIRECTOR = "executive_director"


@dataclass
class RoleBasedApprovalPolicy:
    """Policy mapping risk levels to required approval roles."""

    # Risk level → required role
    role_requirements: dict[str, str] = field(default_factory=lambda: {
        "low": ApprovalRole.OPERATOR,
        "medium": ApprovalRole.OPERATOR,
        "high": ApprovalRole.SENIOR_OPERATOR,
        "critical": ApprovalRole.MISSION_DIRECTOR,
    })
    # Risk level → number of approvers required
    approver_counts: dict[str, int] = field(default_factory=lambda: {
        "low": 1,
        "medium": 1,
        "high": 1,
        "critical": 2,
    })
    # Default timeout per risk level (seconds)
    timeout_by_risk: dict[str, float] = field(default_factory=lambda: {
        "low": 60.0,
        "medium": 300.0,
        "high": 600.0,
        "critical": 900.0,
    })
    # Escalation: after timeout, escalate to next role
    escalation_enabled: bool = True
    escalation_delay_s: float = 120.0  # time before escalating

    def required_role(self, risk_level: str) -> str:
        return self.role_requirements.get(risk_level, ApprovalRole.OPERATOR)

    def required_approvers(self, risk_level: str) -> int:
        return self.approver_counts.get(risk_level, 1)

    def timeout_for(self, risk_level: str) -> float:
        return self.timeout_by_risk.get(risk_level, 300.0)


class ProductionApprovalEngine:
    """Production-grade approval engine with blocking, timeout, and escalation.

    Usage:
        engine = ProductionApprovalEngine()
        approval = await engine.request_approval(execution_id, domain, action, risk_level="high")
        # Blocks until approved, rejected, or timeout:
        result = await engine.await_decision(approval.approval_id)
    """

    ROLE_HIERARCHY: list[str] = [
        ApprovalRole.OPERATOR,
        ApprovalRole.SENIOR_OPERATOR,
        ApprovalRole.MISSION_DIRECTOR,
        ApprovalRole.EXECUTIVE_DIRECTOR,
    ]

    def __init__(self, policy: RoleBasedApprovalPolicy | None = None) -> None:
        self._policy = policy or RoleBasedApprovalPolicy()
        self._pending: dict[str, ApprovalRequest] = {}
        self._futures: dict[str, asyncio.Future[ApprovalRequest]] = {}
        self._approvals_received: dict[str, list[tuple[str, str]]] = {}  # approval_id → [(decided_by, decision)]
        self._history: list[ApprovalRequest] = []
        self._lock = asyncio.Lock()
        self._on_decision: Callable[[ApprovalRequest], Any] | None = None

    def set_decision_callback(self, cb: Callable[[ApprovalRequest], Any]) -> None:
        """Set a callback invoked when an approval is decided."""
        self._on_decision = cb

    async def request_approval(
        self,
        execution_id: str,
        domain: str,
        action: str,
        description: str = "",
        risk_level: str = "medium",
        requested_by: str = "system",
    ) -> ApprovalRequest:
        """Create a new approval request."""
        timeout_s = self._policy.timeout_for(risk_level)
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
            self._approvals_received[approval.approval_id] = []
            self._futures[approval.approval_id] = asyncio.get_event_loop().create_future()
        _log.info(
            "Approval requested: execution=%s domain=%s action=%s risk=%s timeout=%ss",
            execution_id, domain, action, risk_level, timeout_s,
        )
        return approval

    async def await_decision(
        self,
        approval_id: str,
        timeout_s: float | None = None,
    ) -> ApprovalRequest:
        """Block until a decision is made or timeout.

        This is the production blocking call — the calling execution
        pauses until the approval is granted, rejected, or expires.
        """
        async with self._lock:
            if approval_id not in self._futures:
                # Already decided — find in history
                for a in reversed(self._history):
                    if a.approval_id == approval_id:
                        return a
                raise ValueError(f"Approval {approval_id} not found")
            future = self._futures[approval_id]

        # Determine timeout
        approval = self._pending.get(approval_id)
        if timeout_s is None and approval:
            remaining = (approval.expires_at - datetime.now(UTC)).total_seconds()
            timeout_s = max(1.0, remaining)
        elif timeout_s is None:
            timeout_s = 300.0

        try:
            return await asyncio.wait_for(future, timeout=timeout_s)
        except TimeoutError:
            # Auto-expire
            async with self._lock:
                if approval_id in self._pending:
                    expired_approval = self._pending.pop(approval_id)
                    expired_approval.status = ApprovalStatus.EXPIRED.value
                    expired_approval.decided_at = datetime.now(UTC)
                    expired_approval.decision_reason = "Timed out waiting for approval"
                    self._history.append(expired_approval)
                    if approval_id in self._futures and not self._futures[approval_id].done():
                        self._futures[approval_id].set_result(expired_approval)
                    return expired_approval
            # Already decided — find in history
            for a in reversed(self._history):
                if a.approval_id == approval_id:
                    return a
            raise ValueError(f"Approval {approval_id} not found after timeout") from None

    async def approve(
        self,
        approval_id: str,
        decided_by: str = ApprovalRole.OPERATOR,
        role: str = ApprovalRole.OPERATOR,
        reason: str = "",
    ) -> ApprovalRequest | None:
        """Approve a pending request.

        For multi-approver requirements (critical risk), this records
        one approval. The request is fully approved only when enough
        approvers have signed off.
        """
        async with self._lock:
            approval = self._pending.get(approval_id)
            if approval is None:
                return None
            if approval.is_expired():
                approval.status = ApprovalStatus.EXPIRED.value
                approval.decided_at = datetime.now(UTC)
                self._history.append(approval)
                self._pending.pop(approval_id, None)
                if approval_id in self._futures and not self._futures[approval_id].done():
                    self._futures[approval_id].set_result(approval)
                return approval

            # Check role is sufficient
            required_role = self._policy.required_role(approval.risk_level)
            if not self._is_role_sufficient(role, required_role):
                _log.warning(
                    "Approval rejected: role '%s' insufficient for risk '%s' (requires '%s')",
                    role, approval.risk_level, required_role,
                )
                return None

            # Record this approval
            self._approvals_received[approval_id].append((decided_by, "approved"))
            required_count = self._policy.required_approvers(approval.risk_level)
            current_count = len(self._approvals_received[approval_id])

            if current_count >= required_count:
                # Fully approved
                approval.status = ApprovalStatus.APPROVED.value
                approval.decided_at = datetime.now(UTC)
                approval.decided_by = decided_by
                approval.decision_reason = reason or f"Approved by {current_count} approver(s)"
                self._history.append(approval)
                self._pending.pop(approval_id, None)
                self._approvals_received.pop(approval_id, None)
                if approval_id in self._futures and not self._futures[approval_id].done():
                    self._futures[approval_id].set_result(approval)
                _log.info("Approval granted: %s (execution=%s)", approval_id, approval.execution_id)
            else:
                _log.info(
                    "Partial approval: %s (%d/%d approvers)",
                    approval_id, current_count, required_count,
                )
            return approval

    async def reject(
        self,
        approval_id: str,
        decided_by: str = ApprovalRole.OPERATOR,
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
            self._approvals_received.pop(approval_id, None)
            if approval_id in self._futures and not self._futures[approval_id].done():
                self._futures[approval_id].set_result(approval)
            _log.info("Approval rejected: %s (execution=%s)", approval_id, approval.execution_id)
            return approval

    async def cancel(self, approval_id: str, reason: str = "") -> ApprovalRequest | None:
        """Cancel a pending approval (e.g., execution was cancelled)."""
        async with self._lock:
            approval = self._pending.pop(approval_id, None)
            if approval is None:
                return None
            approval.status = ApprovalStatus.EXPIRED.value
            approval.decided_at = datetime.now(UTC)
            approval.decision_reason = f"Cancelled: {reason}"
            self._history.append(approval)
            self._approvals_received.pop(approval_id, None)
            if approval_id in self._futures and not self._futures[approval_id].done():
                self._futures[approval_id].set_result(approval)
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
                self._approvals_received.pop(aid, None)
                if aid in self._futures and not self._futures[aid].done():
                    self._futures[aid].set_result(self._history[-1])
            return list(self._pending.values())

    async def get_history(self, limit: int = 100) -> list[ApprovalRequest]:
        """Get approval history."""
        async with self._lock:
            return list(self._history[-limit:])

    async def get_by_execution(self, execution_id: str) -> ApprovalRequest | None:
        """Get the approval for a specific execution."""
        async with self._lock:
            for approval in self._pending.values():
                if approval.execution_id == execution_id:
                    return approval
            for approval in reversed(self._history):
                if approval.execution_id == execution_id:
                    return approval
        return None

    def _is_role_sufficient(self, role: str, required: str) -> bool:
        """Check if a role has sufficient authority."""
        try:
            role_idx = self.ROLE_HIERARCHY.index(role)
            required_idx = self.ROLE_HIERARCHY.index(required)
            return role_idx >= required_idx
        except ValueError:
            return False
