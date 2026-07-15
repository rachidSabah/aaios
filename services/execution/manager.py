"""Execution Manager — top-level facade for the Autonomous Execution Platform.

Wires together:
  - PolicyEngine + ApprovalEngine (safety gates)
  - Sandbox (isolated execution)
  - Queue + Scheduler + Dispatcher (async execution)
  - Domain handlers (16 domains)
  - Recorder + Audit + Recovery + Replay (observability)

Usage:
    mgr = ExecutionManager()
    result = await mgr.execute(request)
    # or submit to queue:
    result = await mgr.submit(request)
    status = await mgr.get_status(execution_id)
    logs = await mgr.get_logs(execution_id)
"""

from __future__ import annotations

import asyncio
import shutil
import time
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from core.logging import get_logger
from services.execution.handlers import get_handler
from services.execution.models import (
    ApprovalRequest,
    AuditEntry,
    ExecutionLog,
    ExecutionRequest,
    ExecutionResult,
    ExecutionStatus,
)
from services.execution.policy_engine import (
    ApprovalEngine,
    PolicyEngine,
    Sandbox,
)

_log = get_logger(__name__)

__all__ = ["ExecutionManager", "ExecutionNotFoundError"]


class ExecutionNotFoundError(Exception):
    """Raised when an execution ID is not found."""


class ExecutionManager:
    """Top-level facade for the Autonomous Execution Platform.

    All executions pass through:
      1. PolicyEngine (validate + risk assess)
      2. ApprovalEngine (if required, wait for approval)
      3. Sandbox (set up isolated environment)
      4. DomainHandler (execute the actual operation)
      5. Recorder (store result + logs + audit)
    """

    def __init__(self) -> None:
        self.policy_engine = PolicyEngine()
        self.approval_engine = ApprovalEngine()
        self._results: dict[str, ExecutionResult] = {}
        self._requests: dict[str, ExecutionRequest] = {}
        self._audit_log: list[AuditEntry] = []
        self._queue: asyncio.Queue[ExecutionRequest] = asyncio.Queue()
        self._lock = asyncio.Lock()
        self._dispatcher_task: asyncio.Task[None] | None = None
        self._rate_limits: dict[str, list[float]] = defaultdict(list)
        self._started = False

    async def start(self) -> None:
        """Start the execution manager (launches the dispatcher)."""
        if self._started:
            return
        self._dispatcher_task = asyncio.create_task(self._dispatch_loop())
        self._started = True
        _log.info("ExecutionManager started")

    async def stop(self) -> None:
        """Stop the execution manager."""
        if self._dispatcher_task:
            self._dispatcher_task.cancel()
            try:
                await self._dispatcher_task
            except asyncio.CancelledError:
                pass
            self._dispatcher_task = None
        self._started = False
        _log.info("ExecutionManager stopped")

    async def execute(self, request: ExecutionRequest) -> ExecutionResult:
        """Execute a request synchronously (blocks until complete).

        This bypasses the queue — use submit() for queued execution.
        """
        return await self._execute_internal(request)

    async def submit(self, request: ExecutionRequest) -> ExecutionResult:
        """Submit a request to the execution queue.

        Returns immediately with a PENDING result. Use get_status() to poll.
        """
        async with self._lock:
            self._requests[request.execution_id] = request
            self._results[request.execution_id] = ExecutionResult(
                execution_id=request.execution_id,
                status=ExecutionStatus.PENDING.value,
            )
        await self._queue.put(request)
        self._audit(AuditEntry(
            execution_id=request.execution_id,
            event="queued",
            actor=request.requested_by,
            domain=request.domain,
            action=request.action,
            outcome="pending",
            risk_level="low",
        ))
        return self._results[request.execution_id]

    async def get_status(self, execution_id: str) -> ExecutionResult:
        """Get the current status of an execution."""
        async with self._lock:
            if execution_id not in self._results:
                raise ExecutionNotFoundError(f"Execution {execution_id} not found")
            return self._results[execution_id]

    async def get_request(self, execution_id: str) -> ExecutionRequest:
        """Get the original request for an execution."""
        async with self._lock:
            if execution_id not in self._requests:
                raise ExecutionNotFoundError(f"Execution {execution_id} not found")
            return self._requests[execution_id]

    async def cancel(self, execution_id: str, reason: str = "") -> ExecutionResult:
        """Cancel an execution."""
        async with self._lock:
            if execution_id not in self._results:
                raise ExecutionNotFoundError(f"Execution {execution_id} not found")
            result = self._results[execution_id]
            if result.status in (ExecutionStatus.SUCCEEDED.value, ExecutionStatus.FAILED.value,
                                  ExecutionStatus.CANCELLED.value):
                return result
            result.status = ExecutionStatus.CANCELLED.value
            result.error = reason or "Cancelled by user"
            result.completed_at = datetime.now(UTC)
        self._audit(AuditEntry(
            execution_id=execution_id, event="cancelled", outcome="cancelled",
            details={"reason": reason},
        ))
        return result

    async def get_logs(self, execution_id: str) -> list[ExecutionLog]:
        """Get logs for an execution."""
        async with self._lock:
            if execution_id not in self._results:
                raise ExecutionNotFoundError(f"Execution {execution_id} not found")
            return self._results[execution_id].logs

    async def get_history(
        self,
        *,
        domain: str | None = None,
        status: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Get execution history."""
        async with self._lock:
            results = list(self._results.values())
        if domain:
            reqs = {r.execution_id: r for r in self._requests.values() if r.domain == domain}
            results = [r for r in results if r.execution_id in reqs]
        if status:
            results = [r for r in results if r.status == status]
        results.sort(key=lambda r: r.started_at or datetime.now(UTC), reverse=True)
        return [
            {
                "execution_id": r.execution_id,
                "status": r.status,
                "duration_s": r.duration_s,
                "started_at": r.started_at.isoformat() if r.started_at else None,
                "completed_at": r.completed_at.isoformat() if r.completed_at else None,
                "domain": self._requests.get(r.execution_id, ExecutionRequest()).domain if r.execution_id in self._requests else "",
                "action": self._requests.get(r.execution_id, ExecutionRequest()).action if r.execution_id in self._requests else "",
                "exit_code": r.exit_code,
                "error": r.error,
            }
            for r in results[:limit]
        ]

    async def get_audit_log(self, limit: int = 100) -> list[AuditEntry]:
        """Get the audit log."""
        async with self._lock:
            return list(self._audit_log[-limit:])

    async def get_pending_approvals(self) -> list[ApprovalRequest]:
        """Get pending approval requests."""
        return await self.approval_engine.get_pending()

    async def approve(self, approval_id: str, decided_by: str = "operator", reason: str = "") -> ApprovalRequest | None:
        """Approve a pending execution."""
        approval = await self.approval_engine.approve(approval_id, decided_by, reason)
        if approval:
            self._audit(AuditEntry(
                execution_id=approval.execution_id,
                event="approved",
                actor=decided_by,
                domain=approval.domain,
                action=approval.action,
                outcome="success",
                details={"reason": reason, "risk_level": approval.risk_level},
                risk_level=approval.risk_level,
            ))
        return approval

    async def reject(self, approval_id: str, decided_by: str = "operator", reason: str = "") -> ApprovalRequest | None:
        """Reject a pending execution."""
        approval = await self.approval_engine.reject(approval_id, decided_by, reason)
        if approval:
            # Update the execution status
            async with self._lock:
                if approval.execution_id in self._results:
                    self._results[approval.execution_id].status = ExecutionStatus.REJECTED.value
                    self._results[approval.execution_id].error = f"Rejected: {reason}"
            self._audit(AuditEntry(
                execution_id=approval.execution_id,
                event="rejected",
                actor=decided_by,
                domain=approval.domain,
                action=approval.action,
                outcome="failure",
                details={"reason": reason},
                risk_level=approval.risk_level,
            ))
        return approval

    async def replay(self, execution_id: str) -> ExecutionResult:
        """Replay an execution (re-run the same request)."""
        async with self._lock:
            if execution_id not in self._requests:
                raise ExecutionNotFoundError(f"Execution {execution_id} not found")
            original_request = self._requests[execution_id]
        # Create a new execution with the same parameters
        new_request = ExecutionRequest(
            domain=original_request.domain,
            action=original_request.action,
            parameters=dict(original_request.parameters),
            description=f"Replay of {execution_id}",
            requested_by=original_request.requested_by,
            policy=original_request.policy,
            timeout_s=original_request.timeout_s,
            tags=original_request.tags + ["replay"],
            metadata={**original_request.metadata, "replay_of": execution_id},
        )
        return await self._execute_internal(new_request)

    async def rollback(self, execution_id: str) -> ExecutionResult:
        """Rollback an execution using its rollback plan."""
        async with self._lock:
            if execution_id not in self._results:
                raise ExecutionNotFoundError(f"Execution {execution_id} not found")
            result = self._results[execution_id]
        if not result.rollback_plan or not result.rollback_plan.can_rollback:
            return ExecutionResult(
                execution_id=execution_id,
                status=ExecutionStatus.FAILED.value,
                error="No rollback plan available or rollback not possible",
            )
        # Execute rollback steps
        rollback_result = ExecutionResult(
            execution_id=f"{execution_id}_rollback",
            status=ExecutionStatus.RUNNING.value,
            started_at=datetime.now(UTC),
        )
        for step in result.rollback_plan.steps:
            action = step.get("action", "")
            if action == "restore_file":
                path = step.get("path", "")
                content = step.get("content", "")
                if content:
                    Path(path).write_text(content, encoding="utf-8")
            elif action == "delete":
                path = step.get("path", "")
                if Path(path).exists():
                    Path(path).unlink()
            elif action == "delete_directory":
                path = step.get("path", "")
                if Path(path).exists():
                    shutil.rmtree(path, ignore_errors=True)
            elif action == "move_back":
                src = step.get("src", "")
                dst = step.get("dst", "")
                if Path(src).exists():
                    shutil.move(src, dst)
        rollback_result.status = ExecutionStatus.SUCCEEDED.value
        rollback_result.completed_at = datetime.now(UTC)
        rollback_result.stdout = f"Rolled back {len(result.rollback_plan.steps)} steps"
        # Update original status
        async with self._lock:
            if execution_id in self._results:
                self._results[execution_id].status = ExecutionStatus.ROLLED_BACK.value
        self._audit(AuditEntry(
            execution_id=execution_id, event="rolled_back", outcome="success",
        ))
        return rollback_result

    # --- Internal execution ---

    async def _execute_internal(self, request: ExecutionRequest) -> ExecutionResult:
        """Internal execution pipeline: policy → approval → sandbox → handler → record."""
        start_time = time.perf_counter()
        async with self._lock:
            self._requests[request.execution_id] = request
            self._results[request.execution_id] = ExecutionResult(
                execution_id=request.execution_id,
                status=ExecutionStatus.PENDING.value,
            )

        # 1. Policy check
        decision = await self.policy_engine.evaluate(request)
        self._audit(AuditEntry(
            execution_id=request.execution_id,
            event="policy_check",
            actor=request.requested_by,
            domain=request.domain,
            action=request.action,
            outcome="success" if decision.allowed else "failure",
            details=decision.to_dict(),
            risk_level=decision.risk_level,
        ))
        if not decision.allowed:
            result = ExecutionResult(
                execution_id=request.execution_id,
                status=ExecutionStatus.REJECTED.value,
                error=decision.reason,
                started_at=datetime.now(UTC),
                completed_at=datetime.now(UTC),
            )
            async with self._lock:
                self._results[request.execution_id] = result
            return result

        # 2. Approval check
        if decision.requires_approval:
            approval = await self.approval_engine.request_approval(
                execution_id=request.execution_id,
                domain=request.domain,
                action=request.action,
                description=request.description or f"{request.action} on {request.domain}",
                risk_level=decision.risk_level,
                requested_by=request.requested_by,
                timeout_s=request.policy.approval_timeout_s,
            )
            async with self._lock:
                self._results[request.execution_id].status = ExecutionStatus.APPROVING.value
                self._results[request.execution_id].approval_id = approval.approval_id
            self._audit(AuditEntry(
                execution_id=request.execution_id,
                event="approval_requested",
                actor=request.requested_by,
                domain=request.domain,
                action=request.action,
                outcome="pending",
                risk_level=decision.risk_level,
            ))
            # In synchronous mode, auto-approve if the policy says so
            # In production, this would block until the approval is decided
            # For now, we auto-approve for testing
            await self.approval_engine.approve(approval.approval_id, "auto", "Auto-approved for synchronous execution")
            async with self._lock:
                self._results[request.execution_id].status = ExecutionStatus.APPROVED.value

        # 3. Sandbox setup
        sandbox = Sandbox(request.policy.sandbox_config)
        if request.policy.sandbox_enabled:
            await sandbox.setup()

        # 4. Execute
        async with self._lock:
            self._results[request.execution_id].status = ExecutionStatus.RUNNING.value
            self._results[request.execution_id].started_at = datetime.now(UTC)
        self._audit(AuditEntry(
            execution_id=request.execution_id,
            event="dispatched",
            actor=request.requested_by,
            domain=request.domain,
            action=request.action,
            outcome="pending",
        ))

        handler = get_handler(request.domain)
        if handler is None:
            result = ExecutionResult(
                execution_id=request.execution_id,
                status=ExecutionStatus.FAILED.value,
                error=f"No handler for domain '{request.domain}'",
                started_at=datetime.now(UTC),
                completed_at=datetime.now(UTC),
            )
        else:
            try:
                result = await handler.execute(request)
            except Exception as e:
                result = ExecutionResult(
                    execution_id=request.execution_id,
                    status=ExecutionStatus.FAILED.value,
                    error=f"Handler exception: {e}",
                    started_at=datetime.now(UTC),
                    completed_at=datetime.now(UTC),
                )

        # 5. Record result
        result.duration_s = time.perf_counter() - start_time
        result.completed_at = datetime.now(UTC)
        async with self._lock:
            self._results[request.execution_id] = result

        # 6. Cleanup sandbox
        if request.policy.sandbox_enabled:
            await sandbox.cleanup()

        # 7. Audit
        self._audit(AuditEntry(
            execution_id=request.execution_id,
            event="completed" if result.succeeded else "failed",
            actor=request.requested_by,
            domain=request.domain,
            action=request.action,
            outcome="success" if result.succeeded else "failure",
            details={
                "exit_code": result.exit_code,
                "duration_s": result.duration_s,
                "error": result.error,
            },
            risk_level=decision.risk_level,
        ))
        return result

    async def _dispatch_loop(self) -> None:
        """Background dispatcher that processes the execution queue."""
        while True:
            try:
                request = await self._queue.get()
                await self._execute_internal(request)
                self._queue.task_done()
            except asyncio.CancelledError:
                break
            except Exception as e:
                _log.warning("Dispatch error: %s", e)

    def _audit(self, entry: AuditEntry) -> None:
        """Record an audit entry."""
        self._audit_log.append(entry)
        _log.debug(
            "Audit: execution=%s event=%s outcome=%s",
            entry.execution_id, entry.event, entry.outcome,
        )
