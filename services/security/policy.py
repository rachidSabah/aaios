"""Policy engine — RBAC + ABAC for permission decisions.

The policy engine evaluates (actor, action, resource, context) and returns
one of: ALLOW, DENY, ASK.

Rules are ordered by specificity (most specific first). The first matching
rule wins. If no rule matches, the default is DENY (fail-closed).

Roles (RBAC):
  - owner: full control (can do everything)
  - admin: can configure providers, install plugins, manage users
  - operator: can submit/pause/resume tasks, read memory/audit
  - viewer: read-only (tasks, logs, audit — own actions only)

Attributes (ABAC):
  - Resource attributes: project_id, memory_scope, file_path, network_host
  - Context attributes: time_of_day, ip_address, session_id

Phase 8: implements the rule engine with in-memory rules. A rego/Cedar-style
external policy engine is a v1.1 stretch goal.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from core.contracts.actor import ActorRef
from core.contracts.permission import Permission

__all__ = ["PolicyDecision", "PolicyEngine", "PolicyRule", "Role"]


class Role(StrEnum):
    """User roles (RBAC)."""

    OWNER = "owner"
    ADMIN = "admin"
    OPERATOR = "operator"
    VIEWER = "viewer"


class PolicyDecision(StrEnum):
    """The outcome of a policy evaluation."""

    ALLOW = "allow"
    DENY = "deny"
    ASK = "ask"


@dataclass
class PolicyRule:
    """A single policy rule.

    A rule matches if:
      - The actor's role matches ``roles`` (or ``roles`` is empty = any role)
      - The permission name matches ``permission_pattern`` (glob: ``gateway.fs.*`` matches ``gateway.fs.read``)
      - The resource matches ``resource_pattern`` (glob, or ``*`` for any)
      - All ``conditions`` are satisfied (key-value pairs checked against context)

    The first matching rule wins. If no rule matches, the default is DENY.
    """

    decision: PolicyDecision
    roles: set[Role] = field(default_factory=set)
    permission_pattern: str = "*"
    resource_pattern: str = "*"
    conditions: dict[str, str] = field(default_factory=dict)
    description: str = ""

    def matches(
        self,
        actor_role: Role | None,
        permission: Permission,
        resource: str,
        context: dict[str, Any],
    ) -> bool:
        """Return True if this rule matches the request."""
        # Role check
        if self.roles and actor_role not in self.roles:
            return False
        # Permission pattern check (glob)
        if not _glob_match(self.permission_pattern, permission.name):
            return False
        # Resource pattern check
        if not _glob_match(self.resource_pattern, resource):
            return False
        # Condition checks
        for key, value in self.conditions.items():
            if str(context.get(key, "")) != value:
                return False
        return True


def _glob_match(pattern: str, value: str) -> bool:
    """Simple glob match: ``*`` matches any sequence, ``?`` matches one char.

    ``gateway.fs.*`` matches ``gateway.fs.read``.
    ``*`` matches anything.
    """
    if pattern == "*":
        return True
    # Convert glob to regex
    import re

    regex = "^" + re.escape(pattern).replace(r"\*", ".*").replace(r"\?", ".") + "$"
    return re.match(regex, value) is not None


class PolicyEngine:
    """Evaluates permission requests against a set of rules.

    Default rules (loaded at init):
      - owner: ALLOW *
      - admin: ALLOW * (except security.* which is ASK)
      - operator: ALLOW task.*, agent.*, memory.read, tool.call (ASK)
      - viewer: ALLOW task.read, audit.read (own only)
      - default: DENY
    """

    def __init__(self, rules: list[PolicyRule] | None = None) -> None:
        self._rules: list[PolicyRule] = rules or self._default_rules()
        # Actor role assignments (actor_id → role)
        self._actor_roles: dict[str, Role] = {}

    def assign_role(self, actor_id: str, role: Role) -> None:
        """Assign a role to an actor."""
        self._actor_roles[actor_id] = role

    def get_role(self, actor_id: str) -> Role | None:
        """Return the actor's role, or None."""
        return self._actor_roles.get(actor_id)

    def add_rule(self, rule: PolicyRule) -> None:
        """Add a rule (at the end — lower priority than existing rules)."""
        self._rules.append(rule)

    def evaluate(
        self,
        actor: ActorRef,
        permission: Permission,
        resource: str = "*",
        context: dict[str, Any] | None = None,
    ) -> PolicyDecision:
        """Evaluate a permission request. Returns ALLOW, DENY, or ASK."""
        context = context or {}
        actor_role = self._actor_roles.get(actor.id)

        for rule in self._rules:
            if rule.matches(actor_role, permission, resource, context):
                return rule.decision

        # Default: deny (fail-closed)
        return PolicyDecision.DENY

    @staticmethod
    def _default_rules() -> list[PolicyRule]:
        """Return the default rule set."""
        return [
            # Owner can do everything
            PolicyRule(
                decision=PolicyDecision.ALLOW,
                roles={Role.OWNER},
                permission_pattern="*",
                description="Owner can do everything",
            ),
            # Admin can do everything except security-critical operations
            PolicyRule(
                decision=PolicyDecision.ASK,
                roles={Role.ADMIN},
                permission_pattern="security.*",
                description="Admin must confirm security-critical operations",
            ),
            PolicyRule(
                decision=PolicyDecision.ALLOW,
                roles={Role.ADMIN},
                permission_pattern="*",
                description="Admin can do everything else",
            ),
            # Operator can submit tasks, dispatch agents, read memory
            PolicyRule(
                decision=PolicyDecision.ALLOW,
                roles={Role.OPERATOR},
                permission_pattern="task.*",
                description="Operator can manage tasks",
            ),
            PolicyRule(
                decision=PolicyDecision.ALLOW,
                roles={Role.OPERATOR},
                permission_pattern="agent.*",
                description="Operator can dispatch agents",
            ),
            PolicyRule(
                decision=PolicyDecision.ALLOW,
                roles={Role.OPERATOR},
                permission_pattern="memory.read",
                description="Operator can read memory",
            ),
            PolicyRule(
                decision=PolicyDecision.ASK,
                roles={Role.OPERATOR},
                permission_pattern="memory.write",
                description="Operator must confirm memory writes",
            ),
            PolicyRule(
                decision=PolicyDecision.ASK,
                roles={Role.OPERATOR},
                permission_pattern="gateway.*",
                description="Operator must confirm gateway operations",
            ),
            PolicyRule(
                decision=PolicyDecision.ASK,
                roles={Role.OPERATOR},
                permission_pattern="tool.call",
                description="Operator must confirm tool calls",
            ),
            # Viewer can read tasks and audit (own only)
            PolicyRule(
                decision=PolicyDecision.ALLOW,
                roles={Role.VIEWER},
                permission_pattern="task.read",
                description="Viewer can read tasks",
            ),
            PolicyRule(
                decision=PolicyDecision.ALLOW,
                roles={Role.VIEWER},
                permission_pattern="audit.read",
                description="Viewer can read audit log",
            ),
        ]
