"""Tests for the Autonomous Software Engineering Platform (v5.2 Part 1A)."""

from __future__ import annotations

from pathlib import Path

import pytest

from services.engineering import (
    ArchitectureIntelligenceEngine,
    CapabilityRegistry,
    CodeIntelligenceEngine,
    EngCapability,
    EngineeringAgentOrganization,
    EngineeringManager,
    EngineeringWorkspaceManager,
    RepositoryIntelligenceEngine,
)


@pytest.mark.offline
class TestRepositoryIntelligence:
    """RepositoryIntelligenceEngine tests."""

    async def test_discover_repositories(self) -> None:
        engine = RepositoryIntelligenceEngine(Path())
        repos = await engine.discover_repositories()
        assert len(repos) >= 1
        assert repos[0].file_count > 0

    async def test_analyze(self) -> None:
        engine = RepositoryIntelligenceEngine(Path())
        analysis = await engine.analyze()
        assert analysis.total_files > 0
        assert analysis.total_lines > 0
        assert analysis.health_score >= 0
        assert len(analysis.issues) >= 0

    async def test_language_breakdown(self) -> None:
        engine = RepositoryIntelligenceEngine(Path())
        repos = await engine.discover_repositories()
        assert "python" in repos[0].language_breakdown


@pytest.mark.offline
class TestCodeIntelligence:
    """CodeIntelligenceEngine tests."""

    async def test_analyze_python(self, tmp_path: Path) -> None:
        engine = CodeIntelligenceEngine()
        py_file = tmp_path / "test.py"
        py_file.write_text("class Foo:\n    pass\ndef bar():\n    pass\n")
        analysis = await engine.analyze_file(py_file)
        assert analysis.language == "python"
        assert "Foo" in analysis.classes
        assert "bar" in analysis.functions
        assert analysis.complexity_score >= 0.0

    async def test_analyze_typescript(self, tmp_path: Path) -> None:
        engine = CodeIntelligenceEngine()
        ts_file = tmp_path / "test.ts"
        ts_file.write_text("class Bar {}\nfunction baz() {}\nimport { x } from 'mod';\n")
        analysis = await engine.analyze_file(ts_file)
        assert analysis.language == "typescript"
        assert "Bar" in analysis.classes

    async def test_analyze_markdown(self, tmp_path: Path) -> None:
        engine = CodeIntelligenceEngine()
        md_file = tmp_path / "test.md"
        md_file.write_text("# Title\nSome content\n")
        analysis = await engine.analyze_file(md_file)
        assert analysis.language == "markdown"
        assert analysis.line_count == 2

    async def test_complexity_score(self, tmp_path: Path) -> None:
        engine = CodeIntelligenceEngine()
        py_file = tmp_path / "complex.py"
        py_file.write_text("if True:\n  if False:\n    for i in range(10):\n      pass\n")
        analysis = await engine.analyze_file(py_file)
        assert analysis.complexity_score > 0.0


@pytest.mark.offline
class TestArchitectureIntelligence:
    """ArchitectureIntelligenceEngine tests."""

    async def test_inspect(self) -> None:
        engine = ArchitectureIntelligenceEngine(Path())
        recs = await engine.inspect()
        assert isinstance(recs, list)
        for rec in recs:
            assert rec.requires_approval is True
            assert rec.status == "pending"
            assert rec.confidence > 0
            assert rec.reasoning != ""
            assert rec.rollback_strategy != ""

    async def test_recommendations_have_all_fields(self) -> None:
        engine = ArchitectureIntelligenceEngine(Path())
        recs = await engine.inspect()
        for rec in recs:
            d = rec.to_dict()
            assert "confidence" in d
            assert "risk" in d
            assert "impact" in d
            assert "affected_files" in d
            assert "reasoning" in d
            assert "supporting_evidence" in d
            assert "estimated_effort_hours" in d
            assert "rollback_strategy" in d


@pytest.mark.offline
class TestEngineeringAgents:
    """EngineeringAgentOrganization tests."""

    def test_list_agents(self) -> None:
        org = EngineeringAgentOrganization()
        agents = org.list_agents()
        assert len(agents) == 16

    def test_get_agent(self) -> None:
        org = EngineeringAgentOrganization()
        agent = org.get_agent("eng-software-architect-v1")
        assert agent is not None
        assert agent.agent_type == "software_architect"

    def test_find_by_language(self) -> None:
        org = EngineeringAgentOrganization()
        python_agents = org.find_by_language("python")
        assert len(python_agents) > 0

    def test_find_by_framework(self) -> None:
        org = EngineeringAgentOrganization()
        fastapi_agents = org.find_by_framework("fastapi")
        assert len(fastapi_agents) > 0

    def test_select_for_task(self) -> None:
        org = EngineeringAgentOrganization()
        agent = org.select_for_task(language="python", framework="fastapi")
        assert agent is not None

    def test_select_no_match(self) -> None:
        org = EngineeringAgentOrganization()
        agent = org.select_for_task(language="cobol")
        assert agent is None


@pytest.mark.offline
class TestCapabilityRegistry:
    """CapabilityRegistry tests."""

    async def test_register_and_get(self) -> None:
        reg = CapabilityRegistry()
        cap = EngCapability(name="python", category="language", proficiency=0.9)
        registered = await reg.register(cap)
        fetched = await reg.get(registered.capability_id)
        assert fetched is not None
        assert fetched.name == "python"

    async def test_find_by_category(self) -> None:
        reg = CapabilityRegistry()
        await reg.register(EngCapability(name="python", category="language"))
        await reg.register(EngCapability(name="fastapi", category="framework"))
        langs = await reg.find_by_category("language")
        assert len(langs) == 1

    async def test_update_stats(self) -> None:
        reg = CapabilityRegistry()
        cap = await reg.register(EngCapability(name="python", category="language"))
        updated = await reg.update_stats(
            cap.capability_id, success=True, latency_s=1.0, cost_usd=0.01
        )
        assert updated is not None
        assert updated.sample_count == 1
        assert updated.success_rate == 1.0

    async def test_stats(self) -> None:
        reg = CapabilityRegistry()
        await reg.register(EngCapability(name="python", category="language"))
        await reg.register(EngCapability(name="react", category="framework"))
        stats = await reg.stats()
        assert stats["total_capabilities"] == 2


@pytest.mark.offline
class TestEngineeringWorkspace:
    """EngineeringWorkspaceManager tests."""

    async def test_create_and_list(self) -> None:
        mgr = EngineeringWorkspaceManager()
        ws = await mgr.create_workspace("test", ["/repo"])
        assert ws.name == "test"
        workspaces = await mgr.list_workspaces()
        assert len(workspaces) == 1

    async def test_create_session(self) -> None:
        mgr = EngineeringWorkspaceManager()
        ws = await mgr.create_workspace("test", ["/repo"])
        session = await mgr.create_session(ws.workspace_id, "/repo", "main")
        assert session is not None
        assert session.repo_path == "/repo"

    async def test_navigate(self) -> None:
        mgr = EngineeringWorkspaceManager()
        ws = await mgr.create_workspace("test", ["/repo"])
        session = await mgr.create_session(ws.workspace_id, "/repo")
        await mgr.navigate(ws.workspace_id, session.session_id, "/src/main.py")
        ws_after = await mgr.get_workspace(ws.workspace_id)
        assert len(ws_after.sessions[0].navigation_history) == 1

    async def test_delete(self) -> None:
        mgr = EngineeringWorkspaceManager()
        ws = await mgr.create_workspace("test", ["/repo"])
        assert await mgr.delete_workspace(ws.workspace_id) is True
        assert await mgr.delete_workspace(ws.workspace_id) is False


@pytest.mark.offline
class TestEngineeringManager:
    """EngineeringManager integration tests."""

    async def test_analyze_repository(self) -> None:
        mgr = EngineeringManager(Path())
        analysis = await mgr.analyze_repository()
        assert analysis["total_files"] > 0

    async def test_architecture_recommendations(self) -> None:
        mgr = EngineeringManager(Path())
        recs = await mgr.architecture_recommendations()
        assert isinstance(recs, list)

    async def test_list_agents(self) -> None:
        mgr = EngineeringManager(Path())
        agents = mgr.list_engineering_agents()
        assert len(agents) == 16

    async def test_get_overview(self) -> None:
        mgr = EngineeringManager(Path())
        overview = await mgr.get_overview()
        assert overview["repository"]["total_files"] > 0
        assert overview["engineering_agents"] == 16
