"""Tests for the Voice & Vision Agent — capabilities, lifecycle, multimodal methods."""

from __future__ import annotations

from pathlib import Path

import pytest

from agents import VoiceVisionAgent
from agents._impls.voice_vision import build_manifest
from agents._impls.voice_vision.capabilities import CAPABILITY_NAMESPACES
from core.contracts.actor import ActorRef, ActorType
from core.contracts.agent import AgentContext, AgentEnvironment, AgentType
from core.contracts.health import HealthState
from core.contracts.task import TaskContext, TaskRequest, TaskResultStatus


@pytest.fixture
def context() -> AgentContext:
    env = AgentEnvironment(
        home_dir=Path("/tmp"),
        config_dir=Path("/tmp/aaios/config"),
        data_dir=Path("/tmp/aaios/data"),
        log_dir=Path("/tmp/aaios/logs"),
        temp_dir=Path("/tmp/aaios/temp"),
    )
    return AgentContext(environment=env)


@pytest.mark.offline
class TestCapabilityManifest:
    """Capability manifest tests."""

    def test_build_manifest(self) -> None:
        manifest = build_manifest()
        assert manifest.identity.agent_id == "voice-vision-v1"
        assert manifest.identity.agent_type == AgentType.VISION
        assert manifest.identity.implementation_name == "Voice & Vision Agent"
        assert len(manifest.capabilities) == 5

    def test_capability_namespaces(self) -> None:
        assert set(CAPABILITY_NAMESPACES) == {
            "audio.transcribe",
            "audio.synthesize",
            "image.analyze",
            "image.generate",
            "multimodal.chat",
        }

    def test_each_capability_has_permission(self) -> None:
        manifest = build_manifest()
        for cap in manifest.capabilities:
            assert cap.requires_permission is not None, (
                f"Capability {cap.namespace} missing permission"
            )

    def test_resource_requirements(self) -> None:
        manifest = build_manifest()
        assert manifest.resource_requirements.memory_mb >= 1024
        assert manifest.resource_requirements.network is True


@pytest.mark.offline
class TestVoiceVisionAgent:
    """VoiceVisionAgent tests."""

    async def test_initialize_and_discover(self, context: AgentContext) -> None:
        agent = VoiceVisionAgent(mock_mode=True)
        await agent.initialize(context)
        manifest = await agent.discover_capabilities()
        assert manifest.identity.agent_id == "voice-vision-v1"
        assert len(manifest.capabilities) == 5
        await agent.shutdown()

    async def test_transcribe(self) -> None:
        agent = VoiceVisionAgent(mock_mode=True)
        result = await agent.transcribe(b"fake audio bytes")
        assert isinstance(result, str)
        assert len(result) > 0

    async def test_synthesize(self) -> None:
        agent = VoiceVisionAgent(mock_mode=True)
        audio = await agent.synthesize("Hello, world!", voice="alloy")
        assert isinstance(audio, bytes)
        assert len(audio) > 0
        # WAV header starts with "RIFF"
        assert audio[:4] == b"RIFF"

    async def test_analyze_image(self) -> None:
        agent = VoiceVisionAgent(mock_mode=True)
        result = await agent.analyze_image(
            b"fake image bytes",
            prompt="What is in this image?",
        )
        assert isinstance(result, str)
        assert "What is in this image?" in result

    async def test_generate_image(self) -> None:
        agent = VoiceVisionAgent(mock_mode=True)
        image = await agent.generate_image("a red square", size="1024x1024")
        assert isinstance(image, bytes)
        assert len(image) > 0
        # PNG starts with the 8-byte signature
        assert image[:8] == b"\x89PNG\r\n\x1a\n"

    async def test_chat_text_only(self) -> None:
        agent = VoiceVisionAgent(mock_mode=True)
        result = await agent.chat("Hello!")
        assert "Hello!" in result

    async def test_chat_with_image(self) -> None:
        agent = VoiceVisionAgent(mock_mode=True)
        result = await agent.chat("What's this?", image=b"fake image")
        assert "What's this?" in result
        assert "image attached" in result

    async def test_chat_with_audio(self) -> None:
        agent = VoiceVisionAgent(mock_mode=True)
        result = await agent.chat("Listen to this", audio=b"fake audio")
        assert "Listen to this" in result
        assert "audio attached" in result

    async def test_chat_with_both(self) -> None:
        agent = VoiceVisionAgent(mock_mode=True)
        result = await agent.chat(
            "Describe and transcribe",
            image=b"img",
            audio=b"aud",
        )
        assert "image attached" in result
        assert "audio attached" in result

    async def test_execute_task_transcribe(self, context: AgentContext) -> None:
        agent = VoiceVisionAgent(mock_mode=True)
        await agent.initialize(context)
        request = TaskRequest(
            goal="audio.transcribe",
            context=TaskContext(
                submitted_by=ActorRef(type=ActorType.USER, id="alice"),
                metadata={"inputs": {"audio": b"fake audio"}},
            ),
        )
        result = await agent.execute_task(request)
        assert result.status == TaskResultStatus.SUCCESS
        assert isinstance(result.output, dict)
        assert "result" in result.output

    async def test_execute_task_synthesize(self, context: AgentContext) -> None:
        agent = VoiceVisionAgent(mock_mode=True)
        await agent.initialize(context)
        request = TaskRequest(
            goal="audio.synthesize",
            context=TaskContext(
                submitted_by=ActorRef(type=ActorType.USER, id="alice"),
                metadata={"inputs": {"text": "Hello", "voice": "alloy"}},
            ),
        )
        result = await agent.execute_task(request)
        assert result.status == TaskResultStatus.SUCCESS
        assert isinstance(result.output["result"], bytes)

    async def test_execute_task_unknown_capability(self, context: AgentContext) -> None:
        agent = VoiceVisionAgent(mock_mode=True)
        await agent.initialize(context)
        request = TaskRequest(
            goal="nonexistent.capability",
            context=TaskContext(
                submitted_by=ActorRef(type=ActorType.USER, id="alice"),
            ),
        )
        result = await agent.execute_task(request)
        assert result.status == TaskResultStatus.FAILURE
        assert "Unknown capability" in (result.error or "")

    async def test_report_health_no_calls(self) -> None:
        agent = VoiceVisionAgent(mock_mode=True)
        health = await agent.report_health()
        assert health.state == HealthState.HEALTHY

    async def test_report_health_after_calls(self) -> None:
        agent = VoiceVisionAgent(mock_mode=True)
        await agent.transcribe(b"audio")
        await agent.synthesize("text")
        health = await agent.report_health()
        assert health.state in (HealthState.HEALTHY, HealthState.DEGRADED)
        assert "calls=2" in health.reason

    async def test_serialize_state(self) -> None:
        agent = VoiceVisionAgent(mock_mode=True)
        state = await agent.serialize_state()
        # Default InProcessAgent returns empty state
        assert state is not None

    async def test_metrics_tracking(self) -> None:
        agent = VoiceVisionAgent(mock_mode=True)
        assert agent._call_count == 0
        await agent.transcribe(b"audio")
        assert agent._call_count == 1
        await agent.synthesize("text")
        assert agent._call_count == 2
        await agent.analyze_image(b"img", "prompt")
        assert agent._call_count == 3
        await agent.generate_image("prompt")
        assert agent._call_count == 4
        await agent.chat("text")
        assert agent._call_count == 5
        assert agent._total_latency_s >= 0
