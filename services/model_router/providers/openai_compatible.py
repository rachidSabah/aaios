"""OpenAI-compatible provider base — covers 10 of 13 providers.

Providers that use the OpenAI Chat Completions API format:
  OpenAI, Azure OpenAI, OpenRouter, DeepSeek, GLM, NVIDIA, Groq, Mistral,
  LM Studio, Custom

Each of these only differs in:
  - The base URL
  - The API key
  - The model list
  - Minor response format quirks (handled per-provider)

This base class handles the HTTP calls, request/response conversion, streaming,
error handling, and cost calculation. Subclasses just set the base URL, model
list, and cost table.
"""

from __future__ import annotations

import json
import time
from collections.abc import AsyncIterator
from typing import Any

import httpx

from core.contracts.model.health import ProviderHealth, ProviderStatus
from core.contracts.model.message import ModelMessage
from core.contracts.model.request import ModelRequest
from core.contracts.model.response import ModelResponse, ModelStreamChunk, UsageStats
from core.contracts.model.tools import ToolCall
from core.contracts.provider import (
    ModelInfo,
    ProviderConfig,
    ProviderError,
    ProviderType,
    RateLimitError,
)
from core.logging import get_logger

_log = get_logger(__name__)


class OpenAICompatibleProvider:
    """Base class for OpenAI-compatible providers.

    Subclasses MUST set:
      - ``_provider_type`` (ProviderType)
      - ``_default_base_url``
      - ``_model_catalog`` (dict[str, ModelInfo])
    """

    _provider_type: ProviderType = ProviderType.CUSTOM
    _default_base_url: str = "https://api.openai.com/v1"

    # Subclasses override this with their model catalog
    _model_catalog: dict[str, ModelInfo] = {}

    def __init__(self) -> None:
        self._config: ProviderConfig | None = None
        self._client: httpx.AsyncClient | None = None

    @property
    def name(self) -> str:
        """Return the provider name."""
        return self._config.name if self._config else self._provider_type.value

    @property
    def provider_type(self) -> ProviderType:
        """Return the provider type."""
        return self._provider_type

    async def initialize(self, config: ProviderConfig) -> None:
        """Initialize with configuration."""
        self._config = config
        base_url = config.base_url or self._default_base_url
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if config.api_key is not None:
            headers["Authorization"] = f"Bearer {config.api_key.get_secret_value()}"
        # Some providers need extra headers (e.g. OpenRouter needs HTTP-Referer)
        for key, val in config.extra.get("headers", {}).items():
            headers[key] = val
        self._client = httpx.AsyncClient(
            base_url=base_url,
            headers=headers,
            timeout=config.timeout_s,
        )
        _log.info(
            "provider.initialized",
            provider=self.name,
            type=self._provider_type.value,
            base_url=base_url,
        )

    async def shutdown(self) -> None:
        """Release resources."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def list_models(self) -> list[ModelInfo]:
        """Return the models this provider offers."""
        if self._config and self._config.models:
            # Filter the catalog to only the configured models
            return [
                self._model_catalog.get(m, ModelInfo(name=m, provider=self.name))
                for m in self._config.models
            ]
        return list(self._model_catalog.values())

    async def complete(self, request: ModelRequest) -> ModelResponse:
        """Complete a request (non-streaming)."""
        if self._client is None or self._config is None:
            raise ProviderError(self.name, "Provider not initialized")

        model = self._select_model(request)
        payload = self._build_payload(request, model, stream=False)
        start = time.monotonic()

        try:
            response = await self._client.post("/chat/completions", json=payload)
            response.raise_for_status()
        except httpx.HTTPStatusError as e:
            await self._handle_http_error(e)
        except httpx.HTTPError as e:
            raise ProviderError(self.name, f"Network error: {e}", retryable=True) from e

        latency = time.monotonic() - start
        data = response.json()
        return self._parse_response(data, request, latency)

    async def stream(self, request: ModelRequest) -> AsyncIterator[ModelStreamChunk]:
        """Stream a request. Yields chunks."""
        if self._client is None or self._config is None:
            raise ProviderError(self.name, "Provider not initialized")

        model = self._select_model(request)
        payload = self._build_payload(request, model, stream=True)
        request_id = str(request.id)

        try:
            async with self._client.stream("POST", "/chat/completions", json=payload) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    data_str = line[6:]
                    if data_str.strip() == "[DONE]":
                        break
                    try:
                        chunk_data = json.loads(data_str)
                    except json.JSONDecodeError:
                        continue
                    chunk = self._parse_stream_chunk(chunk_data, request_id, model)
                    if chunk is not None:
                        yield chunk
        except httpx.HTTPStatusError as e:
            await self._handle_http_error(e)
        except httpx.HTTPError as e:
            raise ProviderError(self.name, f"Stream error: {e}", retryable=True) from e

    async def health_check(self) -> ProviderHealth:
        """Probe the provider's health by listing models."""
        if self._client is None or self._config is None:
            return ProviderHealth(
                provider=self.name,
                status=ProviderStatus.UNHEALTHY,
                last_error="not initialized",
            )
        try:
            response = await self._client.get("/models", timeout=10.0)
            response.raise_for_status()
            return ProviderHealth(provider=self.name, status=ProviderStatus.HEALTHY)
        except Exception as e:
            return ProviderHealth(
                provider=self.name,
                status=ProviderStatus.UNHEALTHY,
                last_error=str(e),
            )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _select_model(self, request: ModelRequest) -> str:
        """Select the model to use for this request."""
        if request.model_hint:
            return request.model_hint
        # Default: the first model in the catalog
        if self._model_catalog:
            return next(iter(self._model_catalog.keys()))
        return "gpt-4o"  # ultimate fallback

    def _build_payload(self, request: ModelRequest, model: str, *, stream: bool) -> dict[str, Any]:
        """Build the OpenAI-format request payload."""
        payload: dict[str, Any] = {
            "model": model,
            "messages": [self._convert_message(m) for m in request.messages],
            "temperature": request.temperature,
            "stream": stream,
        }
        if request.max_tokens is not None:
            payload["max_tokens"] = request.max_tokens
        if request.top_p != 1.0:
            payload["top_p"] = request.top_p
        if request.stop is not None:
            payload["stop"] = request.stop
        if request.tools is not None:
            payload["tools"] = [
                {
                    "type": "function",
                    "function": {
                        "name": t.name,
                        "description": t.description,
                        "parameters": t.parameters,
                    },
                }
                for t in request.tools
            ]
            if request.tool_choice is not None:
                payload["tool_choice"] = request.tool_choice
        return payload

    def _convert_message(self, msg: ModelMessage) -> dict[str, Any]:
        """Convert a ModelMessage to the OpenAI format."""
        result: dict[str, Any] = {"role": msg.role.value, "content": msg.content}
        if msg.name is not None:
            result["name"] = msg.name
        if msg.tool_calls is not None:
            result["tool_calls"] = msg.tool_calls
        if msg.tool_call_id is not None:
            result["tool_call_id"] = msg.tool_call_id
        return result

    def _parse_response(
        self, data: dict[str, Any], request: ModelRequest, latency_s: float
    ) -> ModelResponse:
        """Parse an OpenAI-format response."""
        choice = data.get("choices", [{}])[0]
        message = choice.get("message", {})
        content = message.get("content", "") or ""
        tool_calls = self._parse_tool_calls(message.get("tool_calls", []))
        usage_data = data.get("usage", {})
        usage = UsageStats(
            prompt_tokens=usage_data.get("prompt_tokens", 0),
            completion_tokens=usage_data.get("completion_tokens", 0),
            total_tokens=usage_data.get("total_tokens", 0),
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
            finish_reason=choice.get("finish_reason", "stop"),
        )

    def _parse_stream_chunk(
        self,
        data: dict[str, Any],
        request_id: str,
        model: str,
    ) -> ModelStreamChunk | None:
        """Parse a streaming chunk."""
        choices = data.get("choices", [])
        if not choices:
            return None
        delta = choices[0].get("delta", {})
        content_delta = delta.get("content", "") or ""
        finish_reason = choices[0].get("finish_reason")
        usage = None
        if "usage" in data:
            usage_data = data["usage"]
            usage = UsageStats(
                prompt_tokens=usage_data.get("prompt_tokens", 0),
                completion_tokens=usage_data.get("completion_tokens", 0),
                total_tokens=usage_data.get("total_tokens", 0),
            )
        return ModelStreamChunk(
            request_id=request_id,
            provider=self.name,
            model=data.get("model", model),
            content_delta=content_delta,
            usage=usage,
            finish_reason=finish_reason,
        )

    def _parse_tool_calls(self, raw_calls: list[dict[str, Any]]) -> list[ToolCall]:
        """Parse tool calls from the OpenAI format."""
        calls: list[ToolCall] = []
        for raw in raw_calls:
            func = raw.get("function", {})
            args_str = func.get("arguments", "{}")
            try:
                args = json.loads(args_str) if isinstance(args_str, str) else args_str
            except json.JSONDecodeError:
                args = {}
            calls.append(
                ToolCall(
                    id=raw.get("id", ""),
                    name=func.get("name", ""),
                    arguments=args,
                ),
            )
        return calls

    def _calculate_cost(self, model: str, usage: UsageStats) -> float:
        """Calculate the cost in USD based on token usage."""
        info = self._model_catalog.get(model)
        if info is None and self._config is not None:
            # Use the provider-level defaults
            input_cost = (usage.prompt_tokens / 1_000_000) * self._config.cost_per_1m_input_usd
            output_cost = (
                usage.completion_tokens / 1_000_000
            ) * self._config.cost_per_1m_output_usd
            return input_cost + output_cost
        if info is None:
            return 0.0
        input_cost = (usage.prompt_tokens / 1_000_000) * info.cost_per_1m_input_usd
        output_cost = (usage.completion_tokens / 1_000_000) * info.cost_per_1m_output_usd
        reasoning_cost = (usage.reasoning_tokens / 1_000_000) * info.cost_per_1m_reasoning_usd
        return input_cost + output_cost + reasoning_cost

    async def _handle_http_error(self, error: httpx.HTTPStatusError) -> None:
        """Handle an HTTP error and raise the appropriate ProviderError."""
        status = error.response.status_code
        body = error.response.text
        if status == 429:
            retry_after = float(error.response.headers.get("Retry-After", 60))
            raise RateLimitError(self.name, retry_after_s=retry_after) from error
        if 500 <= status < 600:
            raise ProviderError(
                self.name,
                f"Server error {status}: {body[:200]}",
                retryable=True,
            ) from error
        raise ProviderError(
            self.name,
            f"Client error {status}: {body[:200]}",
            retryable=False,
        ) from error
