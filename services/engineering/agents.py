"""Engineering Agent Organization + Capability Registry + Workspace.

Phase 6-8: Engineering Agents, Capability Registry, Engineering Workspace.

Defines 16 specialized engineering agents that implement the GenericAgent
interface, a capability registry that indexes programming languages,
frameworks, and engineering domains, and an engineering workspace for
repository sessions.
"""

from __future__ import annotations

import asyncio
from collections import defaultdict
from datetime import UTC, datetime
from typing import Any

from core.logging import get_logger
from services.engineering.models import (
    EngCapability,
    EngineeringAgentManifest,
    EngWorkspace,
    EngWorkspaceSession,
)

_log = get_logger(__name__)

__all__ = [
    "CapabilityRegistry",
    "EngineeringAgentOrganization",
    "EngineeringWorkspaceManager",
]


# 16 specialized engineering agents
ENGINEERING_AGENTS: list[EngineeringAgentManifest] = [
    EngineeringAgentManifest(
        agent_id="eng-software-architect-v1",
        agent_type="software_architect",
        display_name="Software Architect Agent",
        description="Designs system architecture, evaluates trade-offs, recommends patterns",
        languages=["python", "typescript", "go", "java"],
        frameworks=["fastapi", "react", "kubernetes"],
    ),
    EngineeringAgentManifest(
        agent_id="eng-tech-lead-v1",
        agent_type="tech_lead",
        display_name="Technical Lead Agent",
        description="Reviews code, enforces standards, guides engineering decisions",
        languages=["python", "typescript"],
        frameworks=["pytest", "eslint"],
    ),
    EngineeringAgentManifest(
        agent_id="eng-backend-engineer-v1",
        agent_type="backend_engineer",
        display_name="Backend Engineer Agent",
        description="Implements server-side logic, APIs, databases, integrations",
        languages=["python", "go", "java", "rust"],
        frameworks=["fastapi", "django", "spring"],
    ),
    EngineeringAgentManifest(
        agent_id="eng-frontend-engineer-v1",
        agent_type="frontend_engineer",
        display_name="Frontend Engineer Agent",
        description="Implements UI components, pages, client-side logic",
        languages=["typescript", "javascript", "css", "html"],
        frameworks=["react", "next.js", "tailwind"],
    ),
    EngineeringAgentManifest(
        agent_id="eng-database-engineer-v1",
        agent_type="database_engineer",
        display_name="Database Engineer Agent",
        description="Designs schemas, writes migrations, optimizes queries",
        languages=["sql", "python"],
        frameworks=["postgresql", "sqlite", "redis"],
    ),
    EngineeringAgentManifest(
        agent_id="eng-infrastructure-engineer-v1",
        agent_type="infrastructure_engineer",
        display_name="Infrastructure Engineer Agent",
        description="Manages servers, networking, storage, containers",
        languages=["shell", "python", "yaml"],
        frameworks=["docker", "kubernetes", "terraform"],
    ),
    EngineeringAgentManifest(
        agent_id="eng-cloud-engineer-v1",
        agent_type="cloud_engineer",
        display_name="Cloud Engineer Agent",
        description="Deploys and manages cloud resources across providers",
        languages=["python", "yaml", "shell"],
        frameworks=["aws", "azure", "gcp"],
    ),
    EngineeringAgentManifest(
        agent_id="eng-security-engineer-v1",
        agent_type="security_engineer",
        display_name="Security Engineer Agent",
        description="Audits code, detects vulnerabilities, enforces security policies",
        languages=["python", "shell"],
        frameworks=["bandit", "semgrep", "snyk"],
    ),
    EngineeringAgentManifest(
        agent_id="eng-performance-engineer-v1",
        agent_type="performance_engineer",
        display_name="Performance Engineer Agent",
        description="Profiles, benchmarks, and optimizes application performance",
        languages=["python", "go"],
        frameworks=["pytest-benchmark", "py-spy"],
    ),
    EngineeringAgentManifest(
        agent_id="eng-qa-engineer-v1",
        agent_type="qa_engineer",
        display_name="QA Engineer Agent",
        description="Writes and runs tests, manages test coverage, reports defects",
        languages=["python", "typescript"],
        frameworks=["pytest", "playwright", "vitest"],
    ),
    EngineeringAgentManifest(
        agent_id="eng-devops-engineer-v1",
        agent_type="devops_engineer",
        display_name="DevOps Engineer Agent",
        description="Manages CI/CD pipelines, deployments, monitoring",
        languages=["yaml", "shell", "python"],
        frameworks=["github-actions", "jenkins", "gitlab-ci"],
    ),
    EngineeringAgentManifest(
        agent_id="eng-release-engineer-v1",
        agent_type="release_engineer",
        display_name="Release Engineer Agent",
        description="Manages releases, versioning, changelogs, rollbacks",
        languages=["python", "shell"],
        frameworks=["semantic-release", "git"],
    ),
    EngineeringAgentManifest(
        agent_id="eng-documentation-engineer-v1",
        agent_type="documentation_engineer",
        display_name="Documentation Engineer Agent",
        description="Writes and maintains documentation, API references, guides",
        languages=["markdown", "python"],
        frameworks=["mkdocs", "sphinx"],
    ),
    EngineeringAgentManifest(
        agent_id="eng-api-engineer-v1",
        agent_type="api_engineer",
        display_name="API Engineer Agent",
        description="Designs and implements REST/GraphQL/gRPC APIs",
        languages=["python", "typescript"],
        frameworks=["fastapi", "openapi", "graphql"],
    ),
    EngineeringAgentManifest(
        agent_id="eng-code-review-engineer-v1",
        agent_type="code_review_engineer",
        display_name="Code Review Engineer Agent",
        description="Reviews pull requests, enforces coding standards",
        languages=["python", "typescript", "go"],
        frameworks=["ruff", "eslint", "golangci-lint"],
    ),
    EngineeringAgentManifest(
        agent_id="eng-testing-engineer-v1",
        agent_type="testing_engineer",
        display_name="Testing Engineer Agent",
        description="Designs test strategies, writes integration/e2e/stress tests",
        languages=["python", "typescript"],
        frameworks=["pytest", "playwright", "locust"],
    ),
]


class EngineeringAgentOrganization:
    """Manages the 16 specialized engineering agents.

    Phase 6: Software Engineering Agent Organization.
    Each agent implements GenericAgent and advertises a CapabilityManifest.
    The Supervisor selects agents by capability only (INV-09).
    """

    def __init__(self) -> None:
        self._agents: dict[str, EngineeringAgentManifest] = {
            a.agent_id: a for a in ENGINEERING_AGENTS
        }
        self._by_type: dict[str, list[str]] = defaultdict(list)
        for agent in ENGINEERING_AGENTS:
            self._by_type[agent.agent_type].append(agent.agent_id)

    def list_agents(self) -> list[EngineeringAgentManifest]:
        """List all engineering agents."""
        return list(self._agents.values())

    def get_agent(self, agent_id: str) -> EngineeringAgentManifest | None:
        """Get an agent by ID."""
        return self._agents.get(agent_id)

    def find_by_type(self, agent_type: str) -> list[EngineeringAgentManifest]:
        """Find agents by type."""
        return [self._agents[aid] for aid in self._by_type.get(agent_type, []) if aid in self._agents]

    def find_by_language(self, language: str) -> list[EngineeringAgentManifest]:
        """Find agents that support a given language."""
        return [a for a in self._agents.values() if language in a.languages]

    def find_by_framework(self, framework: str) -> list[EngineeringAgentManifest]:
        """Find agents that support a given framework."""
        return [a for a in self._agents.values() if framework in a.frameworks]

    def select_for_task(
        self,
        *,
        language: str | None = None,
        framework: str | None = None,
        agent_type: str | None = None,
    ) -> EngineeringAgentManifest | None:
        """Select the best agent for a task based on criteria."""
        candidates = list(self._agents.values())
        if agent_type:
            candidates = [a for a in candidates if a.agent_type == agent_type]
        if language:
            candidates = [a for a in candidates if language in a.languages]
        if framework:
            candidates = [a for a in candidates if framework in a.frameworks]
        return candidates[0] if candidates else None


class CapabilityRegistry:
    """Indexes engineering capabilities across languages, frameworks, domains.

    Phase 7: Engineering Capability Registry.
    """

    CATEGORIES: list[str] = [
        "language", "framework", "database", "cloud", "testing",
        "package_manager", "build_system", "deployment", "os", "pattern", "domain",
    ]

    def __init__(self) -> None:
        self._capabilities: dict[str, EngCapability] = {}
        self._by_category: dict[str, list[str]] = defaultdict(list)
        self._lock = asyncio.Lock()

    async def register(self, capability: EngCapability) -> EngCapability:
        async with self._lock:
            self._capabilities[capability.capability_id] = capability
            self._by_category[capability.category].append(capability.capability_id)
        return capability

    async def get(self, capability_id: str) -> EngCapability | None:
        async with self._lock:
            return self._capabilities.get(capability_id)

    async def find_by_category(self, category: str) -> list[EngCapability]:
        async with self._lock:
            return [self._capabilities[cid] for cid in self._by_category.get(category, []) if cid in self._capabilities]

    async def find_by_name(self, name: str) -> EngCapability | None:
        async with self._lock:
            for cap in self._capabilities.values():
                if cap.name == name:
                    return cap
            return None

    async def update_stats(
        self,
        capability_id: str,
        *,
        success: bool,
        latency_s: float,
        cost_usd: float,
    ) -> EngCapability | None:
        """Update capability statistics after an execution."""
        async with self._lock:
            cap = self._capabilities.get(capability_id)
            if cap is None:
                return None
            n = cap.sample_count
            cap.success_rate = (cap.success_rate * n + (1.0 if success else 0.0)) / (n + 1)
            cap.avg_latency_s = (cap.avg_latency_s * n + latency_s) / (n + 1)
            cap.avg_cost_usd = (cap.avg_cost_usd * n + cost_usd) / (n + 1)
            cap.sample_count = n + 1
            return cap

    async def list_all(self) -> list[EngCapability]:
        async with self._lock:
            return list(self._capabilities.values())

    async def stats(self) -> dict[str, Any]:
        async with self._lock:
            by_cat: dict[str, int] = {}
            for cat, ids in self._by_category.items():
                by_cat[cat] = len(ids)
            return {
                "total_capabilities": len(self._capabilities),
                "by_category": by_cat,
            }


class EngineeringWorkspaceManager:
    """Manages engineering workspaces for repository sessions.

    Phase 8: Engineering Workspace.
    """

    def __init__(self) -> None:
        self._workspaces: dict[str, EngWorkspace] = {}
        self._lock = asyncio.Lock()

    async def create_workspace(
        self,
        name: str,
        repo_paths: list[str],
    ) -> EngWorkspace:
        ws = EngWorkspace(name=name, repo_paths=list(repo_paths))
        async with self._lock:
            self._workspaces[ws.workspace_id] = ws
        return ws

    async def get_workspace(self, workspace_id: str) -> EngWorkspace | None:
        async with self._lock:
            return self._workspaces.get(workspace_id)

    async def list_workspaces(self) -> list[EngWorkspace]:
        async with self._lock:
            return list(self._workspaces.values())

    async def create_session(
        self,
        workspace_id: str,
        repo_path: str,
        branch: str = "main",
        mission_id: str | None = None,
    ) -> EngWorkspaceSession | None:
        async with self._lock:
            ws = self._workspaces.get(workspace_id)
            if ws is None:
                return None
            session = EngWorkspaceSession(
                repo_path=repo_path,
                branch=branch,
                mission_id=mission_id,
            )
            ws.sessions.append(session)
            return session

    async def navigate(self, workspace_id: str, session_id: str, path: str) -> None:
        """Record navigation in a workspace session."""
        async with self._lock:
            ws = self._workspaces.get(workspace_id)
            if ws is None:
                return
            for session in ws.sessions:
                if session.session_id == session_id:
                    session.navigation_history.append(path)
                    session.last_active = datetime.now(UTC)
                    break

    async def delete_workspace(self, workspace_id: str) -> bool:
        async with self._lock:
            return self._workspaces.pop(workspace_id, None) is not None
