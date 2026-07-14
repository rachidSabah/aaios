"""Capability manifest for the Claude Code CodingAgent.

Advertises: code.read, code.write, code.refactor, code.review, test.run,
git.commit, git.push, git.branch, shell.execute.

Claude Code is one implementation of the CodingAgent type. Future
implementations (OpenHands, Cline, Roo Code, Gemini CLI, Codex CLI) would
advertise the same capabilities but via their own agent packages.
"""

from __future__ import annotations

from core.contracts.agent import (
    AgentIdentity,
    AgentType,
    Capability,
    CapabilityManifest,
    CostModel,
    HealthCheckSpec,
    ResourceRequirements,
    SideEffect,
    TimeoutDefaults,
)
from core.contracts.permission import Permission

__all__ = ["build_manifest", "CAPABILITIES", "CAPABILITY_NAMESPACES"]


# Capability namespaces this agent advertises
CAPABILITY_NAMESPACES = [
    "code.read",
    "code.write",
    "code.refactor",
    "code.review",
    "test.run",
    "git.commit",
    "git.push",
    "git.branch",
    "shell.execute",
]


CAPABILITIES: list[Capability] = [
    Capability(
        namespace="code.read",
        description="Read source code files from the project sandbox",
        side_effects=[SideEffect(kind="fs.read", scope="project")],
        requires_permission=Permission(name="gateway.fs.read"),
    ),
    Capability(
        namespace="code.write",
        description="Write or modify source code files in the project sandbox",
        side_effects=[SideEffect(kind="fs.write", scope="project")],
        requires_permission=Permission(name="gateway.fs.write"),
    ),
    Capability(
        namespace="code.refactor",
        description="Refactor code: rename, extract, inline, restructure",
        side_effects=[SideEffect(kind="fs.write", scope="project")],
        requires_permission=Permission(name="gateway.fs.write"),
    ),
    Capability(
        namespace="code.review",
        description="Review a code diff and return comments + verdict",
        side_effects=[SideEffect(kind="fs.read", scope="project")],
        requires_permission=Permission(name="gateway.fs.read"),
    ),
    Capability(
        namespace="test.run",
        description="Run the project test suite",
        side_effects=[SideEffect(kind="shell.exec", scope="project")],
        requires_permission=Permission(name="gateway.shell.exec"),
    ),
    Capability(
        namespace="git.commit",
        description="Create a git commit",
        side_effects=[SideEffect(kind="shell.exec", scope="project")],
        requires_permission=Permission(name="gateway.shell.exec"),
    ),
    Capability(
        namespace="git.push",
        description="Push commits to the remote repository",
        side_effects=[
            SideEffect(kind="shell.exec", scope="project"),
            SideEffect(kind="net.request", scope="git-host"),
        ],
        requires_permission=Permission(name="gateway.shell.exec"),
    ),
    Capability(
        namespace="git.branch",
        description="Create, list, or switch git branches",
        side_effects=[SideEffect(kind="shell.exec", scope="project")],
        requires_permission=Permission(name="gateway.shell.exec"),
    ),
    Capability(
        namespace="shell.execute",
        description="Execute a shell command in the project sandbox",
        side_effects=[SideEffect(kind="shell.exec", scope="project")],
        requires_permission=Permission(name="gateway.shell.exec"),
    ),
]


def build_manifest() -> CapabilityManifest:
    """Build the capability manifest for the Claude Code agent.

    Note: the identity uses a generic ID 'claude-code-v1'. The actual
    claude CLI is never referenced by name in the core (INV-09).
    """
    identity = AgentIdentity(
        agent_id="claude-code-v1",
        agent_type=AgentType.CODING,
        implementation_name="Claude Code",
        version="1.0.0",
        vendor="Anthropic",
        signature=None,
    )
    return CapabilityManifest(
        identity=identity,
        capabilities=CAPABILITIES,
        resource_requirements=ResourceRequirements(
            cpu_cores=2.0,
            memory_mb=512,
            disk_mb=100,
            network=True,
        ),
        permissions_required=[
            Permission(name="gateway.fs.read", resource="project"),
            Permission(name="gateway.fs.write", resource="project"),
            Permission(name="gateway.shell.exec", resource="project"),
        ],
        health_check=HealthCheckSpec(
            interval_s=30,
            timeout_s=5,
            unhealthy_threshold=3,
            degraded_threshold=1,
        ),
        timeout_defaults=TimeoutDefaults(
            initialize_s=30.0,
            discover_capabilities_s=5.0,
            execute_task_s=600.0,
            cancel_task_s=5.0,
            report_health_s=5.0,
        ),
        cost_model=CostModel(
            per_token_usd=0.000015,
            per_second_usd=0.0,
        ),
    )
