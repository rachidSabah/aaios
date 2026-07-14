"""Anthropic provider — uses the Anthropic Messages API format.

Different from OpenAI:
  - System message is a top-level parameter, not a message in the list
  - Tool calling format is slightly different
  - Prompt caching via cache_control
  - Extended thinking (reasoning) support
"""

from __future__ import annotations

import json
import time
from collections.abc import AsyncIterator
from typing import Any

import httpx

from core.contracts.model.health import ProviderHealth, ProviderStatus
from core.contracts.model.request import ModelRequest
from core.contracts.model.response import ModelResponse, ModelStreamChunk, UsageStats
from core.contracts.model.tools import ToolCall
from core.contracts.provider import (
    ModelInfo,
    ProviderConfig,
    ProviderError,
    ProviderType,
)
from core.logging import get_logger
from services.model_router.providers.openai_compatible import OpenAICompatibleProvider

_log = get_logger(__name__)


class AnthropicProvider(OpenAICompatibleProvider):
    """Anthropic provider — Claude models via the Messages API.

    Extends OpenAICompatibleProvider but overrides ``complete``, ``stream``,
    ``_build_payload``, and ``_parse_response`` to use the Anthropic API format.
    """

    _provider_type = ProviderType.ANTHROPIC
    _default_base_url = "https://api.anthropic.com/v1"

    _model_catalog: dict[str, ModelInfo] = {
        "claude-3-5-sonnet-20241022": ModelInfo(
            name="claude-3-5-sonnet-20241022",
            display_name="Claude 3.5 Sonnet",
            provider="anthropic",
            supports_vision=True,
            supports_tools=True,
            supports_streaming=True,
            supports_caching=True,
            context_window=200_000,
            max_output_tokens=8_192,
            cost_per_1m_input_usd=3.00,
            cost_per_1m_output_usd=15.00,
        ),
        "claude-3-5-haiku-20241022": ModelInfo(
            name="claude-3-5-haiku-20241022",
            display_name="Claude 3.5 Haiku",
            provider="anthropic",
            supports_vision=True,
            supports_tools=True,
            supports_streaming=True,
            supports_caching=True,
            context_window=200_000,
            max_output_tokens=8_192,
            cost_per_1m_input_usd=0.80,
            cost_per_1m_output_usd=4.00,
        ),
        "claude-3-opus-20240229": ModelInfo(
            name="claude-3-opus-20240229",
            display_name="Claude 3 Opus",
            provider="anthropic",
            supports_vision=True,
            supports_tools=True,
            supports_streaming=True,
            supports_caching=True,
            context_window=200_000,
            max_output_tokens=4_096,
            cost_per_1m_input_usd=15.00,
            cost_per_1m_output_usd=75.00,
        ),
    }

    async def initialize(self, config: ProviderConfig) -> None:
        """Initialize with Anthropic-specific headers."""
        # Anthropic uses x-api-key instead of Bearer token
        if config.api_key is not None:
            if not config.extra.get("headers"):
                config.extra["headers"] = {}
            config.extra["headers"]["x-api-key"] = config.api_key.get_secret_value()
            config.extra["headers"]["anthropic-version"] = "2023-06-01"
        await super().initialize(config)

    async def complete(self, request: ModelRequest) -> ModelResponse:
        """Complete using the Anthropic Messages API."""
        if self._client is None or self._config is None:
            raise ProviderError(self.name, "Provider not initialized")

        model = self._select_model(request)
        payload = self._build_payload(request, model, stream=False)
        start = time.monotonic()

        try:
            response = await self._client.post("/messages", json=payload)
            response.raise_for_status()
        except httpx.HTTPStatusError as e:
            await self._handle_http_error(e)
        except httpx.HTTPError as e:
            raise ProviderError(self.name, f"Network error: {e}", retryable=True) from e

        latency = time.monotonic() - start
        data = response.json()
        return self._parse_response(data, request, latency)

    async def stream(self, request: ModelRequest) -> AsyncIterator[ModelStreamChunk]:
        """Stream using the Anthropic Messages API."""
        if self._client is None or self._config is None:
            raise ProviderError(self.name, "Provider not initialized")

        model = self._select_model(request)
        payload = self._build_payload(request, model, stream=True)
        request_id = str(request.id)

        try:
            async with self._client.stream("POST", "/messages", json=payload) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    data_str = line[6:]
                    try:
                        chunk_data = json.loads(data_str)
                    except json.JSONDecodeError:
                        continue
                    chunk = self._parse_anthropic_stream_chunk(chunk_data, request_id, model)
                    if chunk is not None:
                        yield chunk
        except httpx.HTTPStatusError as e:
            await self._handle_http_error(e)
        except httpx.HTTPError as e:
            raise ProviderError(self.name, f"Stream error: {e}", retryable=True) from e

    def _build_payload(self, request: ModelRequest, model: str, *, stream: bool) -> dict[str, Any]:
        """Build the Anthropic Messages API payload.

        Anthropic puts the system message as a top-level ``system`` parameter,
        and the remaining messages in ``messages``.
        """
        # Extract the system message
        system_text = ""
        messages: list[dict[str, Any]] = []
        for msg in request.messages:
            if msg.role.value == "system":
                if isinstance(msg.content, str):
                    system_text = msg.content
            else:
                messages.append({"role": msg.role.value, "content": msg.content})

        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "max_tokens": request.max_tokens or 4096,
            "stream": stream,
        }
        if system_text:
            payload["system"] = system_text
        if request.temperature != 0.7:
            payload["temperature"] = request.temperature
        if request.top_p != 1.0:
            payload["top_p"] = request.top_p
        if request.stop is not None:
            payload["stop_sequences"] = request.stop
        if request.tools is not None:
            payload["tools"] = [
                {
                    "name": t.name,
                    "description": t.description,
                    "input_schema": t.parameters,
                }
                for t in request.tools
            ]
        # Prompt caching (if cache_key is set)
        if request.cache_key and "system" in payload:
            payload["system"] = [
                {"type": "text", "text": payload["system"], "cache_control": {"type": "ephemeral"}},
            ]
        return payload

    def _parse_response(
        self, data: dict[str, Any], request: ModelRequest, latency_s: float
    ) -> ModelResponse:
        """Parse the Anthropic response format."""
        content_blocks = data.get("content", [])
        text_parts: list[str] = []
        tool_calls: list[ToolCall] = []
        for block in content_blocks:
            if block.get("type") == "text":
                text_parts.append(block.get("text", ""))
            elif block.get("type") == "tool_use":
                tool_calls.append(
                    ToolCall(
                        id=block.get("id", ""),
                        name=block.get("name", ""),
                        arguments=block.get("input", {}),
                    ),
                )
        content = "".join(text_parts)
        usage_data = data.get("usage", {})
        usage = UsageStats(
            prompt_tokens=usage_data.get("input_tokens", 0),
            completion_tokens=usage_data.get("output_tokens", 0),
            total_tokens=usage_data.get("input_tokens", 0) + usage_data.get("output_tokens", 0),
            cached_tokens=usage_data.get("cache_read_input_tokens", 0),
        )
        model = data.get("model", self._select_model(request))
        cost = self._calculate_cost(model, usage)

        return ModelResponse(
            request_id=str(request.id),
            provider=self.name,
            model=model,
            content=content,
            tool_calls=tool_calls,
            usage=usage,
            cost_usd=cost,
            latency_s=latency_s,
            finish_reason=data.get("stop_reason", "stop"),
        )

    def _parse_anthropic_stream_chunk(
        self,
        data: dict[str, Any],
        request_id: str,
        model: str,
    ) -> ModelStreamChunk | None:
        """Parse an Anthropic streaming event."""
        event_type = data.get("type", "")
        if event_type == "content_block_delta":
            delta = data.get("delta", {})
            if delta.get("type") == "text_delta":
                return ModelStreamChunk(
                    request_id=request_id,
                    provider=self.name,
                    model=model,
                    content_delta=delta.get("text", ""),
                )
        elif event_type == "message_delta":
            delta = data.get("delta", {})
            usage_data = data.get("usage", {})
            usage = None
            if usage_data:
                usage = UsageStats(
                    prompt_tokens=0,
                    completion_tokens=usage_data.get("output_tokens", 0),
                    total_tokens=usage_data.get("output_tokens", 0),
                )
            return ModelStreamChunk(
                request_id=request_id,
                provider=self.name,
                model=model,
                finish_reason=delta.get("stop_reason"),
                usage=usage,
            )
        return None

    async def health_check(self) -> ProviderHealth:
        """Probe Anthropic's health with a minimal request."""
        if self._client is None or self._config is None:
            return ProviderHealth(
                provider=self.name,
                status=ProviderStatus.UNHEALTHY,
                last_error="not initialized",
            )
        try:
            # Anthropic doesn't have a /models endpoint; send a minimal message
            response = await self._client.post(
                "/messages",
                json={
                    "model": "claude-3-5-haiku-20241022",
                    "max_tokens": 1,
                    "messages": [{"role": "user", "content": "hi"}],
                },
                timeout=10.0,
            )
            if response.status_code in (200, 400):
                return ProviderHealth(provider=self.name, status=ProviderStatus.HEALTHY)
            return ProviderHealth(
                provider=self.name,
                status=ProviderStatus.UNHEALTHY,
                last_error=f"HTTP {response.status_code}",
            )
        except Exception as e:
            return ProviderHealth(
                provider=self.name,
                status=ProviderStatus.UNHEALTHY,
                last_error=str(e),
            )
