"""Network gateway — the only place that makes HTTP requests.

All HTTP/HTTPS goes through here. The gateway:
  1. Checks the destination against the egress allow-list.
  2. Asks the permission checker.
  3. Performs the request via ``httpx``.
  4. Audit-logs the call (URL, method, status — never the body).
"""

from __future__ import annotations

import time
from typing import Any

import httpx

from core.contracts.actor import ActorRef
from core.contracts.permission import Permission
from core.gateway.audit import AuditEntry, get_audit_logger
from core.gateway.permission import get_permission_checker
from core.logging import get_logger

_log = get_logger(__name__)


class NetworkGateway:
    """Network gateway — egress-allow-listed, permission-checked, audit-logged."""

    DEFAULT_TIMEOUT_S: float = 30.0
    MAX_RESPONSE_BYTES: int = 16 * 1024 * 1024  # 16 MB

    def __init__(self, allowed_hosts: list[str] | None = None) -> None:
        """Initialize the network gateway.

        Args:
            allowed_hosts: list of allowed hostnames. ``'*'`` allows all.
                If None, defaults to allowing only ``localhost`` and ``127.0.0.1``.
        """
        self._allowed_hosts = (
            set(allowed_hosts) if allowed_hosts is not None else {"localhost", "127.0.0.1"}
        )

    def add_allowed_host(self, host: str) -> None:
        """Add a host to the egress allow-list."""
        self._allowed_hosts.add(host)

    def is_host_allowed(self, host: str) -> bool:
        """Return True if ``host`` is in the egress allow-list."""
        if "*" in self._allowed_hosts:
            return True
        return host in self._allowed_hosts

    async def request(
        self,
        method: str,
        url: str,
        *,
        actor: ActorRef,
        body: bytes | str | None = None,
        headers: dict[str, str] | None = None,
        timeout_s: float | None = None,
    ) -> dict[str, Any]:
        """Make an HTTP request.

        Returns a dict with keys: status_code, headers, body (bytes), elapsed_s.

        Raises PermissionError if the host is not allowed or permission is denied.
        """
        # Parse URL to extract host
        try:
            from urllib.parse import urlparse

            parsed = urlparse(url)
            host = parsed.hostname or ""
        except (ValueError, AttributeError):
            host = ""

        if not self.is_host_allowed(host):
            await self._audit(actor, f"gateway.net.request {method}", url, False, "egress_denied")
            raise PermissionError(f"Egress to {host} not in allow-list")

        checker = get_permission_checker()
        result = await checker.check(
            actor,
            Permission(name="gateway.net.request", resource=f"{method} {url[:256]}"),
        )
        if result.decision.value == "deny":
            await self._audit(actor, f"gateway.net.request {method}", url, False, "denied")
            raise PermissionError(f"Permission denied: net request {method} {url}")

        timeout = timeout_s or self.DEFAULT_TIMEOUT_S
        start = time.monotonic()
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.request(
                    method=method,
                    url=url,
                    content=body if isinstance(body, bytes) else (body.encode() if body else None),
                    headers=headers,
                )
        except httpx.HTTPError as e:
            duration = time.monotonic() - start
            await self._audit(actor, f"gateway.net.request {method}", url, False, str(e))
            raise

        duration = time.monotonic() - start
        await self._audit(
            actor,
            f"gateway.net.request {method}",
            url,
            response.is_success,
            f"status={response.status_code} duration={duration:.2f}s",
        )
        return {
            "status_code": response.status_code,
            "headers": dict(response.headers),
            "body": response.content[: self.MAX_RESPONSE_BYTES],
            "elapsed_s": duration,
        }

    async def _audit(
        self,
        actor: ActorRef,
        action: str,
        target: str,
        success: bool,
        reason: str,
    ) -> None:
        """Emit an audit entry."""
        logger = get_audit_logger()
        try:
            await logger.log(
                AuditEntry(
                    actor=actor,
                    action=action,
                    target=target[:512],
                    success=success,
                    reason=reason,
                ),
            )
        except Exception:
            _log.exception("gateway.audit_failed", action=action, target=target[:256])


# Singleton
_INSTANCE: NetworkGateway | None = None


def get_net_gateway() -> NetworkGateway:
    """Return the singleton network gateway."""
    global _INSTANCE
    if _INSTANCE is None:
        _INSTANCE = NetworkGateway()
    return _INSTANCE
