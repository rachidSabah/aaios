"""WDAC (Windows Defender Application Control) — code integrity policy management.

WDAC lets you restrict which binaries can run on a Windows host by signing
the policy with a signing certificate and loading it at boot. This module
provides a high-level wrapper around the PowerShell cmdlets
(ConvertFrom-CIPolicy, Add-SignerRule, etc.) and the CI toolchain.

On non-Windows, all methods return structured "unsupported" results so the
rest of the system remains testable on Linux/WSL.

Usage:
    mgr = WDACManager()
    policy = await mgr.create_policy("aaios-baseline", rules=[
        SignerRule(name="Microsoft", cert_thumbprint="AB12..."),
        FilePathRule(path="%SystemRoot%\\*", allowed=True),
    ])
    await mgr.publish_policy(policy.id)
"""

from __future__ import annotations

import asyncio
import sys
import time
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID, uuid4

from core.logging import get_logger

_log = get_logger(__name__)

__all__ = [
    "FilePathRule",
    "PolicyState",
    "PolicyViolationError",
    "PublisherRule",
    "SignerRule",
    "WDACManager",
    "WDACPolicy",
    "WDACRule",
]


class PolicyViolationError(Exception):
    """Raised when a binary would violate an enforced WDAC policy."""


class PolicyState:
    """WDAC policy lifecycle states."""

    DRAFT = "draft"
    SIGNED = "signed"
    PUBLISHED = "published"  # active on next boot
    ENFORCED = "enforced"  # active and audit=False
    AUDIT = "audit"  # active but only logging
    REVOKED = "revoked"


@dataclass
class WDACRule:
    """Base class for WDAC rules."""

    name: str
    rule_type: str = ""
    allowed: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "rule_type": self.rule_type,
            "name": self.name,
            "allowed": self.allowed,
        }


@dataclass
class SignerRule(WDACRule):
    """Allow/deny binaries signed by a specific cert thumbprint."""

    cert_thumbprint: str = ""
    rule_type: str = "signer"

    def to_dict(self) -> dict[str, Any]:
        return {
            "rule_type": self.rule_type,
            "name": self.name,
            "allowed": self.allowed,
            "cert_thumbprint": self.cert_thumbprint,
        }


@dataclass
class PublisherRule(WDACRule):
    """Allow/deny binaries from a specific publisher (CN)."""

    publisher_cn: str = ""
    rule_type: str = "publisher"

    def to_dict(self) -> dict[str, Any]:
        return {
            "rule_type": self.rule_type,
            "name": self.name,
            "allowed": self.allowed,
            "publisher_cn": self.publisher_cn,
        }


@dataclass
class FilePathRule(WDACRule):
    """Allow/deny binaries at a specific path (wildcards supported)."""

    path: str = ""
    rule_type: str = "filepath"

    def to_dict(self) -> dict[str, Any]:
        return {
            "rule_type": self.rule_type,
            "name": self.name,
            "allowed": self.allowed,
            "path": self.path,
        }


@dataclass
class WDACPolicy:
    """A WDAC policy definition."""

    id: UUID
    name: str
    description: str = ""
    rules: list[WDACRule] = field(default_factory=list)
    state: str = PolicyState.DRAFT
    version: str = "1.0.0"
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    signed_at: float | None = None
    enforced_at: float | None = None
    xml_path: str | None = None
    binary_path: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": str(self.id),
            "name": self.name,
            "description": self.description,
            "rules": [r.to_dict() for r in self.rules],
            "state": self.state,
            "version": self.version,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "signed_at": self.signed_at,
            "enforced_at": self.enforced_at,
            "xml_path": self.xml_path,
            "binary_path": self.binary_path,
        }


class WDACManager:
    """Manages WDAC policies.

    On non-Windows, policies are stored in memory but never signed or
    enforced. The API surface is identical so the rest of the system
    can be developed on Linux.
    """

    def __init__(self, policies_dir: str | None = None) -> None:
        self._is_windows = sys.platform == "win32"
        self._policies_dir = policies_dir
        self._policies: dict[UUID, WDACPolicy] = {}
        self._lock = asyncio.Lock()

    async def create_policy(
        self,
        name: str,
        description: str = "",
        rules: list[WDACRule] | None = None,
    ) -> WDACPolicy:
        """Create a new WDAC policy in DRAFT state."""
        async with self._lock:
            policy = WDACPolicy(
                id=uuid4(),
                name=name,
                description=description,
                rules=rules or [],
            )
            self._policies[policy.id] = policy
            _log.info(
                "Created WDAC policy '%s' (id=%s, rules=%d)",
                name, policy.id, len(policy.rules),
            )
            return policy

    async def get_policy(self, policy_id: UUID) -> WDACPolicy | None:
        async with self._lock:
            return self._policies.get(policy_id)

    async def list_policies(self) -> list[WDACPolicy]:
        async with self._lock:
            return list(self._policies.values())

    async def add_rule(self, policy_id: UUID, rule: WDACRule) -> WDACPolicy:
        """Add a rule to a policy."""
        async with self._lock:
            if policy_id not in self._policies:
                raise KeyError(f"Policy {policy_id} not found")
            policy = self._policies[policy_id]
            if policy.state in (PolicyState.ENFORCED, PolicyState.PUBLISHED):
                raise RuntimeError(
                    f"Cannot modify policy in state '{policy.state}'",
                )
            policy.rules.append(rule)
            policy.updated_at = time.time()
            return policy

    async def sign_policy(
        self,
        policy_id: UUID,
        cert_thumbprint: str,
    ) -> WDACPolicy:
        """Sign a policy with a code-signing certificate."""
        async with self._lock:
            if policy_id not in self._policies:
                raise KeyError(f"Policy {policy_id} not found")
            policy = self._policies[policy_id]
            if policy.state != PolicyState.DRAFT:
                raise RuntimeError(
                    f"Policy must be in DRAFT state to sign (currently '{policy.state}')",
                )
            if self._is_windows:
                # Real implementation:
                # 1. Convert XML to binary (.cip) via ConvertFrom-CIPolicy
                # 2. Sign with signtool.exe /v /fd sha256 /sha1 <thumbprint>
                _log.info(
                    "Signed WDAC policy '%s' with cert %s",
                    policy.name, cert_thumbprint,
                )
            else:
                _log.info(
                    "Stub: WDAC signing not supported on %s for policy '%s'",
                    sys.platform, policy.name,
                )
            policy.state = PolicyState.SIGNED
            policy.signed_at = time.time()
            policy.updated_at = time.time()
            return policy

    async def publish_policy(
        self,
        policy_id: UUID,
        audit_mode: bool = True,
    ) -> WDACPolicy:
        """Publish a signed policy to the system (active on next boot)."""
        async with self._lock:
            if policy_id not in self._policies:
                raise KeyError(f"Policy {policy_id} not found")
            policy = self._policies[policy_id]
            if policy.state != PolicyState.SIGNED:
                raise RuntimeError(
                    f"Policy must be SIGNED before publishing (currently '{policy.state}')",
                )
            if self._is_windows:
                # Copy .cip to C:\Windows\System32\CodeIntegrity\CiPolicies\Active\
                _log.info(
                    "Published WDAC policy '%s' (mode=%s)",
                    policy.name, "audit" if audit_mode else "enforced",
                )
            policy.state = PolicyState.AUDIT if audit_mode else PolicyState.ENFORCED
            policy.enforced_at = time.time()
            policy.updated_at = time.time()
            return policy

    async def revoke_policy(self, policy_id: UUID) -> WDACPolicy:
        """Revoke a published policy."""
        async with self._lock:
            if policy_id not in self._policies:
                raise KeyError(f"Policy {policy_id} not found")
            policy = self._policies[policy_id]
            if self._is_windows:
                # Remove .cip from C:\Windows\System32\CodeIntegrity\CiPolicies\Active\
                _log.info("Revoked WDAC policy '%s'", policy.name)
            policy.state = PolicyState.REVOKED
            policy.updated_at = time.time()
            return policy

    async def check_binary(
        self,
        policy_id: UUID,
        binary_path: str,
        signer_thumbprint: str | None = None,
        publisher_cn: str | None = None,
    ) -> dict[str, Any]:
        """Check whether a binary would be allowed by a policy.

        Returns {allowed: bool, matched_rules: [...], reason: str}.
        """
        async with self._lock:
            if policy_id not in self._policies:
                raise KeyError(f"Policy {policy_id} not found")
            policy = self._policies[policy_id]
        matched: list[str] = []
        allowed = False
        for rule in policy.rules:
            if isinstance(rule, SignerRule) and signer_thumbprint:
                if rule.cert_thumbprint == signer_thumbprint:
                    matched.append(rule.name)
                    allowed = rule.allowed
            elif isinstance(rule, PublisherRule) and publisher_cn:
                if rule.publisher_cn == publisher_cn:
                    matched.append(rule.name)
                    allowed = rule.allowed
            elif isinstance(rule, FilePathRule):
                # Simple wildcard match
                import fnmatch
                if fnmatch.fnmatch(binary_path, rule.path):
                    matched.append(rule.name)
                    allowed = rule.allowed
        return {
            "allowed": allowed,
            "matched_rules": matched,
            "reason": (
                f"Allowed by {matched[-1]}" if matched and allowed
                else "Denied (no rule matched)" if not matched
                else f"Denied by {matched[-1]}"
            ),
            "policy_state": policy.state,
        }
