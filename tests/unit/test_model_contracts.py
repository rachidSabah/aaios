"""Tests for the model router contracts — messages, requests, responses, tools."""

from __future__ import annotations

import pytest

from core.contracts.model import (
    ModelMessage,
    ModelRequest,
    ModelResponse,
    ModelRole,
    ModelStreamChunk,
    ProviderConfig,
    ProviderType,
    ToolCall,
    ToolDefinition,
    UsageStats,
)


@pytest.mark.offline
class TestModelMessage:
    """ModelMessage tests."""

    def test_system_factory(self) -> None:
        msg = ModelMessage.system("You are a helpful assistant")
        assert msg.role == ModelRole.SYSTEM
        assert msg.content == "You are a helpful assistant"

    def test_user_factory(self) -> None:
        msg = ModelMessage.user("Hello")
        assert msg.role == ModelRole.USER
        assert msg.content == "Hello"

    def test_assistant_factory(self) -> None:
        msg = ModelMessage.assistant("Hi there")
        assert msg.role == ModelRole.ASSISTANT

    def test_tool_factory(self) -> None:
        msg = ModelMessage.tool("call-123", '{"result": 42}')
        assert msg.role == ModelRole.TOOL
        assert msg.tool_call_id == "call-123"

    def test_multimodal_content(self) -> None:
        msg = ModelMessage(
            role=ModelRole.USER,
            content=[
                {"type": "text", "text": "What is this?"},
                {"type": "image_url", "image_url": {"url": "data:image/png;base64,..."}},
            ],
        )
        assert isinstance(msg.content, list)
        assert len(msg.content) == 2


@pytest.mark.offline
class TestModelRequest:
    """ModelRequest tests."""

    def test_basic_request(self) -> None:
        req = ModelRequest(messages=[ModelMessage.user("Hello")])
        assert req.id is not None
        assert len(req.messages) == 1
        assert req.temperature == 0.7
        assert req.model_hint is None

    def test_with_model_hint(self) -> None:
        req = ModelRequest(
            messages=[ModelMessage.user("Hi")],
            model_hint="gpt-4o",
            provider_hint="openai",
        )
        assert req.model_hint == "gpt-4o"
        assert req.provider_hint == "openai"

    def test_with_tools(self) -> None:
        tool = ToolDefinition(
            name="get_weather",
            description="Get the weather for a city",
            parameters={
                "type": "object",
                "properties": {"city": {"type": "string"}},
                "required": ["city"],
            },
        )
        req = ModelRequest(
            messages=[ModelMessage.user("What is the weather in Paris?")],
            tools=[tool],
            tool_choice="auto",
        )
        assert len(req.tools) == 1
        assert req.tools[0].name == "get_weather"
        assert req.tool_choice == "auto"

    def test_max_cost(self) -> None:
        req = ModelRequest(
            messages=[ModelMessage.user("Hi")],
            max_cost_usd=0.50,
        )
        assert req.max_cost_usd == 0.50


@pytest.mark.offline
class TestModelResponse:
    """ModelResponse tests."""

    def test_basic_response(self) -> None:
        resp = ModelResponse(
            request_id="req-1",
            provider="openai",
            model="gpt-4o",
            content="Hello!",
        )
        assert resp.provider == "openai"
        assert resp.content == "Hello!"
        assert resp.cost_usd == 0.0
        assert resp.finish_reason == "stop"

    def test_with_tool_calls(self) -> None:
        call = ToolCall(id="call-1", name="get_weather", arguments={"city": "Paris"})
        resp = ModelResponse(
            request_id="req-1",
            provider="openai",
            model="gpt-4o",
            content="",
            tool_calls=[call],
            finish_reason="tool_calls",
        )
        assert len(resp.tool_calls) == 1
        assert resp.tool_calls[0].name == "get_weather"

    def test_usage_stats(self) -> None:
        usage = UsageStats(
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150,
            cached_tokens=20,
        )
        assert usage.prompt_tokens == 100
        assert usage.cached_tokens == 20


@pytest.mark.offline
class TestProviderConfig:
    """ProviderConfig tests."""

    def test_openai_config(self) -> None:
        from pydantic import SecretStr

        config = ProviderConfig(
            type=ProviderType.OPENAI,
            name="openai",
            api_key=SecretStr("sk-test"),
            priority=1,
        )
        assert config.type == ProviderType.OPENAI
        assert config.enabled is True
        assert config.priority == 1
        assert config.api_key is not None
        assert config.api_key.get_secret_value() == "sk-test"

    def test_ollama_config_no_key(self) -> None:
        config = ProviderConfig(
            type=ProviderType.OLLAMA,
            name="ollama",
            base_url="http://localhost:11434/v1",
        )
        assert config.api_key is None
        assert config.base_url == "http://localhost:11434/v1"


@pytest.mark.offline
class TestModelStreamChunk:
    """ModelStreamChunk tests."""

    def test_content_delta(self) -> None:
        chunk = ModelStreamChunk(
            request_id="req-1",
            provider="openai",
            model="gpt-4o",
            content_delta="Hello",
        )
        assert chunk.content_delta == "Hello"
        assert chunk.finish_reason is None
        assert chunk.usage is None

    def test_final_chunk_with_usage(self) -> None:
        usage = UsageStats(prompt_tokens=10, completion_tokens=5, total_tokens=15)
        chunk = ModelStreamChunk(
            request_id="req-1",
            provider="openai",
            model="gpt-4o",
            content_delta="",
            usage=usage,
            finish_reason="stop",
        )
        assert chunk.usage is not None
        assert chunk.usage.total_tokens == 15
        assert chunk.finish_reason == "stop"


@pytest.mark.offline
class TestProviderTypes:
    """Verify all 13 provider types exist."""

    def test_all_13_types(self) -> None:
        types = list(ProviderType)
        assert len(types) == 13
        expected = {
            "openai",
            "anthropic",
            "google",
            "openrouter",
            "deepseek",
            "glm",
            "nvidia",
            "ollama",
            "lm_studio",
            "azure_openai",
            "mistral",
            "groq",
            "custom",
        }
        assert {t.value for t in types} == expected
