"""Tests for the agent contracts — identity, context, state, manifest, metrics."""

from __future__ import annotations

from pathlib import Path

import pytest

from core.contracts.agent import (
    AgentContext,
    AgentEnvironment,
    AgentIdentity,
    AgentState,
    AgentType,
    Capability,
    CapabilityManifest,
    CostEstimate,
    MetricsReport,
    SideEffect,
    StateIncompatibleError,
)
from core.contracts.permission import Permission


@pytest.mark.offline
class TestAgentIdentity:
    """AgentIdentity tests."""

    def test_basic_identity(self) -> None:
        ident = AgentIdentity(
            agent_id="mock-coding-v1",
            agent_type=AgentType.CODING,
            implementation_name="Mock Coding Agent",
            version="1.0.0",
        )
        assert ident.agent_id == "mock-coding-v1"
        assert ident.agent_type == AgentType.CODING
        assert ident.vendor == "AAiOS"  # default
        assert ident.signature is None  # default

    def test_frozen(self) -> None:
        ident = AgentIdentity(
            agent_id="x",
            agent_type=AgentType.CUSTOM,
            implementation_name="X",
            version="1.0.0",
        )
        with pytest.raises(Exception):
            ident.agent_id = "y"  # type: ignore[misc]

    def test_str_format(self) -> None:
        ident = AgentIdentity(
            agent_id="x-v1",
            agent_type=AgentType.CODING,
            implementation_name="X",
            version="1.0.0",
            vendor="TestCo",
        )
        s = str(ident)
        assert "x-v1" in s
        assert "Coding" in s  # agent_type.value.title()
        assert "1.0.0" in s
        assert "TestCo" in s

    def test_all_16_agent_types_exist(self) -> None:
        """The taxonomy must have exactly 16 types."""
        types = list(AgentType)
        assert len(types) == 16
        expected = {
            "supervisor",
            "planner",
            "coding",
            "desktop",
            "research",
            "browser",
            "memory",
            "reflection",
            "qa",
            "security",
            "deployment",
            "vision",
            "voice",
            "document",
            "workflow",
            "custom",
        }
        assert {t.value for t in types} == expected


@pytest.mark.offline
class TestAgentState:
    """AgentState tests."""

    def test_default_state(self) -> None:
        state = AgentState(agent_id="x")
        assert state.format == "1"
        assert state.data == {}

    def test_equality(self) -> None:
        s1 = AgentState(agent_id="x", format="1", data={"k": "v"})
        s2 = AgentState(agent_id="x", format="1", data={"k": "v"})
        s3 = AgentState(agent_id="x", format="1", data={"k": "other"})
        assert s1 == s2
        assert s1 != s3

    def test_state_incompatible_error(self) -> None:
        err = StateIncompatibleError("agent-x", "2", "1")
        assert err.agent_id == "agent-x"
        assert err.current_format == "2"
        assert err.snapshot_format == "1"
        assert "agent-x" in str(err)


@pytest.mark.offline
class TestCapabilityManifest:
    """CapabilityManifest tests."""

    def test_empty_manifest(self) -> None:
        ident = AgentIdentity(
            agent_id="x",
            agent_type=AgentType.CUSTOM,
            implementation_name="X",
            version="1.0.0",
        )
        manifest = CapabilityManifest(identity=ident)
        assert manifest.capabilities == []
        assert not manifest.has_capability("anything")
        assert manifest.capability_namespaces() == []

    def test_manifest_with_capabilities(self) -> None:
        ident = AgentIdentity(
            agent_id="x",
            agent_type=AgentType.CODING,
            implementation_name="X",
            version="1.0.0",
        )
        cap1 = Capability(namespace="code.read", description="Read files")
        cap2 = Capability(namespace="code.write", description="Write files")
        manifest = CapabilityManifest(identity=ident, capabilities=[cap1, cap2])
        assert manifest.has_capability("code.read")
        assert manifest.has_capability("code.write")
        assert not manifest.has_capability("code.refactor")
        assert manifest.capability_namespaces() == ["code.read", "code.write"]

    def test_capability_with_permission_and_side_effects(self) -> None:
        cap = Capability(
            namespace="gateway.fs.write",
            requires_permission=Permission(name="gateway.fs.write", resource="/tmp"),
            side_effects=[SideEffect(kind="fs.write", scope="/tmp/")],
            cost_estimate=CostEstimate(avg_usd=0.001, avg_latency_s=0.05),
        )
        assert cap.requires_permission.name == "gateway.fs.write"
        assert cap.side_effects[0].kind == "fs.write"
        assert cap.cost_estimate.avg_usd == 0.001


@pytest.mark.offline
class TestMetricsReport:
    """MetricsReport tests."""

    def test_defaults(self) -> None:
        report = MetricsReport(agent_id="x")
        assert report.tasks_completed == 0
        assert report.tokens_consumed == 0
        assert report.cost_usd == 0.0

    def test_success_rate_no_tasks(self) -> None:
        report = MetricsReport(agent_id="x")
        assert report.success_rate == 1.0  # no tasks → 100% by convention

    def test_success_rate_with_failures(self) -> None:
        report = MetricsReport(
            agent_id="x",
            tasks_completed=8,
            tasks_failed=2,
        )
        assert report.success_rate == 0.8


@pytest.mark.offline
class TestAgentContext:
    """AgentContext tests."""

    def test_default_context(self) -> None:
        env = AgentEnvironment(
            home_dir=Path("/home/user"),
            config_dir=Path("/etc/aaios"),
            data_dir=Path("/var/lib/aaios"),
            log_dir=Path("/var/log/aaios"),
            temp_dir=Path("/tmp/aaios"),
        )
        ctx = AgentContext(environment=env)
        assert ctx.bus is None
        assert ctx.gateway is None
        assert ctx.task_correlation_id is None

    def test_derive_for_task(self) -> None:
        from uuid import uuid4

        env = AgentEnvironment(
            home_dir=Path("/home"),
            config_dir=Path("/etc"),
            data_dir=Path("/var"),
            log_dir=Path("/var/log"),
            temp_dir=Path("/tmp"),
        )
        ctx = AgentContext(environment=env)
        task_id = uuid4()
        derived = ctx.derive_for_task(task_id)
        assert derived.task_correlation_id == task_id
        # Original unchanged
        assert ctx.task_correlation_id is None
