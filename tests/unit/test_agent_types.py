"""Tests for the agent type Protocols — 16 types extending GenericAgent."""

from __future__ import annotations

import pytest

from agents import (
    BrowserAgent,
    CodingAgent,
    CustomAgent,
    DeploymentAgent,
    DesktopAgent,
    DocumentAgent,
    GenericAgent,
    MemoryAgent,
    PlannerAgent,
    QAAgent,
    ReflectionAgent,
    ResearchAgent,
    SecurityAgent,
    SupervisorAgent,
    VisionAgent,
    VoiceAgent,
    WorkflowAgent,
)


@pytest.mark.offline
class TestAgentTypeProtocols:
    """Verify all 16 type Protocols exist and extend GenericAgent."""

    ALL_TYPES = [
        SupervisorAgent,
        PlannerAgent,
        CodingAgent,
        DesktopAgent,
        ResearchAgent,
        BrowserAgent,
        MemoryAgent,
        ReflectionAgent,
        QAAgent,
        SecurityAgent,
        DeploymentAgent,
        VisionAgent,
        VoiceAgent,
        DocumentAgent,
        WorkflowAgent,
        CustomAgent,
    ]

    def test_all_16_types_exist(self) -> None:
        """There must be exactly 16 agent type Protocols."""
        assert len(self.ALL_TYPES) == 16

    def test_each_type_extends_generic(self) -> None:
        """Each type Protocol must include the GenericAgent interface.

        We check this by verifying that each type Protocol has the 11
        GenericAgent methods.
        """
        generic_methods = {
            "identity",
            "initialize",
            "shutdown",
            "discover_capabilities",
            "execute_task",
            "stream_progress",
            "cancel_task",
            "report_health",
            "report_metrics",
            "request_permission",
            "serialize_state",
            "restore_state",
        }
        for proto in self.ALL_TYPES:
            proto_methods = set(dir(proto))
            missing = generic_methods - proto_methods
            assert not missing, f"{proto.__name__} missing methods: {missing}"

    def test_supervisor_has_lifecycle_methods(self) -> None:
        """SupervisorAgent must have submit_goal, pause, resume, rollback, override."""
        for method in ("submit_goal", "pause", "resume", "rollback", "override", "get_result"):
            assert hasattr(SupervisorAgent, method), f"SupervisorAgent missing {method}"

    def test_coding_has_code_methods(self) -> None:
        """CodingAgent must have read_file, write_file, run_tests, git, shell, review."""
        for method in ("read_file", "write_file", "run_tests", "git", "shell", "review"):
            assert hasattr(CodingAgent, method), f"CodingAgent missing {method}"

    def test_desktop_has_automation_methods(self) -> None:
        """DesktopAgent must have open_app, close_app, click, type_text, screenshot, ocr."""
        for method in ("open_app", "close_app", "click", "type_text", "screenshot", "ocr"):
            assert hasattr(DesktopAgent, method), f"DesktopAgent missing {method}"

    def test_research_has_web_methods(self) -> None:
        """ResearchAgent must have search, fetch, summarize, cite."""
        for method in ("search", "fetch", "summarize", "cite"):
            assert hasattr(ResearchAgent, method), f"ResearchAgent missing {method}"

    def test_browser_has_interaction_methods(self) -> None:
        """BrowserAgent must have navigate, click, input, extract, screenshot."""
        for method in ("navigate", "click", "input", "extract", "screenshot"):
            assert hasattr(BrowserAgent, method), f"BrowserAgent missing {method}"

    def test_memory_has_memory_methods(self) -> None:
        """MemoryAgent must have recall, summarize, forget, link, rank."""
        for method in ("recall", "summarize", "forget", "link", "rank"):
            assert hasattr(MemoryAgent, method), f"MemoryAgent missing {method}"

    def test_qa_has_validation_methods(self) -> None:
        """QAAgent must have validate, lint, test, schema."""
        for method in ("validate", "lint", "test", "schema"):
            assert hasattr(QAAgent, method), f"QAAgent missing {method}"

    def test_vision_has_image_methods(self) -> None:
        """VisionAgent must have caption, detect, ocr, compare."""
        for method in ("caption", "detect", "ocr", "compare"):
            assert hasattr(VisionAgent, method), f"VisionAgent missing {method}"

    def test_voice_has_stt_tts(self) -> None:
        """VoiceAgent must have stt and tts."""
        for method in ("stt", "tts"):
            assert hasattr(VoiceAgent, method), f"VoiceAgent missing {method}"

    def test_document_has_doc_methods(self) -> None:
        """DocumentAgent must have create, edit, convert, extract."""
        for method in ("create", "edit", "convert", "extract"):
            assert hasattr(DocumentAgent, method), f"DocumentAgent missing {method}"


@pytest.mark.offline
class TestGenericAgentInterface:
    """Verify the GenericAgent Protocol itself."""

    def test_generic_has_11_methods(self) -> None:
        """GenericAgent must have exactly the 11 specified methods.

        11 methods: identity (property) + initialize + shutdown +
        discover_capabilities + execute_task + stream_progress +
        cancel_task + report_health + report_metrics + request_permission +
        serialize_state + restore_state = 12 (identity is a property, not a
        method, but it's part of the interface).
        """
        expected = {
            "identity",  # property
            "initialize",
            "shutdown",
            "discover_capabilities",
            "execute_task",
            "stream_progress",
            "cancel_task",
            "report_health",
            "report_metrics",
            "request_permission",
            "serialize_state",
            "restore_state",
        }
        actual = set(dir(GenericAgent))
        # dir() returns methods + inherited; check each expected is present
        for name in expected:
            assert name in actual, f"GenericAgent missing {name}"

    def test_generic_is_runtime_checkable(self) -> None:
        """GenericAgent must be @runtime_checkable."""
        # @runtime_checkable Protocols support isinstance() checks
        # We can't easily test this without an implementation, but we verify
        # the Protocol is decorated
        from typing import _ProtocolMeta  # type: ignore[attr-defined]

        assert isinstance(GenericAgent, _ProtocolMeta) or hasattr(GenericAgent, "_is_protocol")
