"""Google Gemini provider — uses the Gemini API format.

Different from OpenAI:
  - Endpoint: /v1beta/models/{model}:generateContent
  - Message format is different (parts, role: user/model)
  - Tool calling uses functionDeclarations
"""

from __future__ import annotations

import time
from collections.abc import AsyncIterator
from typing import Any

import httpx

from core.contracts.model.health import ProviderHealth, ProviderStatus
from core.contracts.model.message import ModelRole
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


class GoogleProvider(OpenAICompatibleProvider):
    """Google Gemini provider.

    Extends OpenAICompatibleProvider but overrides the API calls to use
    the Gemini format.
    """

    _provider_type = ProviderType.GOOGLE
    _default_base_url = "https://generativelanguage.googleapis.com/v1beta"

    _model_catalog: dict[str, ModelInfo] = {
        "gemini-1.5-pro": ModelInfo(
            name="gemini-1.5-pro",
            display_name="Gemini 1.5 Pro",
            provider="google",
            supports_vision=True,
            supports_tools=True,
            supports_streaming=True,
            context_window=2_000_000,
            max_output_tokens=8_192,
            cost_per_1m_input_usd=1.25,
            cost_per_1m_output_usd=5.00,
        ),
        "gemini-1.5-flash": ModelInfo(
            name="gemini-1.5-flash",
            display_name="Gemini 1.5 Flash",
            provider="google",
            supports_vision=True,
            supports_tools=True,
            supports_streaming=True,
            context_window=1_000_000,
            max_output_tokens=8_192,
            cost_per_1m_input_usd=0.075,
            cost_per_1m_output_usd=0.30,
        ),
        "gemini-2.0-flash": ModelInfo(
            name="gemini-2.0-flash",
            display_name="Gemini 2.0 Flash",
            provider="google",
            supports_vision=True,
            supports_tools=True,
            supports_streaming=True,
            context_window=1_000_000,
            max_output_tokens=8_192,
            cost_per_1m_input_usd=0.10,
            cost_per_1m_output_usd=0.40,
        ),
    }

    async def initialize(self, config: ProviderConfig) -> None:
        """Initialize with Google-specific auth (API key as query param)."""
        await super().initialize(config)

    async def complete(self, request: ModelRequest) -> ModelResponse:
        """Complete using the Gemini API."""
        if self._client is None or self._config is None:
            raise ProviderError(self.name, "Provider not initialized")

        model = self._select_model(request)
        payload = self._build_payload(request, model)
        api_key = self._config.api_key.get_secret_value() if self._config.api_key else ""
        start = time.monotonic()

        try:
            response = await self._client.post(
                f"/models/{model}:generateContent?key={api_key}",
                json=payload,
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as e:
            await self._handle_http_error(e)
        except httpx.HTTPError as e:
            raise ProviderError(self.name, f"Network error: {e}", retryable=True) from e

        latency = time.monotonic() - start
        data = response.json()
        return self._parse_response(data, request, latency)

    async def stream(self, request: ModelRequest) -> AsyncIterator[ModelStreamChunk]:
        """Stream using the Gemini API (streamGenerateContent)."""
        if self._client is None or self._config is None:
            raise ProviderError(self.name, "Provider not initialized")

        model = self._select_model(request)
        payload = self._build_payload(request, model)
        api_key = self._config.api_key.get_secret_value() if self._config.api_key else ""
        request_id = str(request.id)

        try:
            async with self._client.stream(
                "POST",
                f"/models/{model}:streamGenerateContent?key={api_key}&alt=sse",
                json=payload,
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    import json

                    data = json.loads(line[6:])
                    chunk = self._parse_gemini_stream_chunk(data, request_id, model)
                    if chunk is not None:
                        yield chunk
        except httpx.HTTPStatusError as e:
            await self._handle_http_error(e)
        except httpx.HTTPError as e:
            raise ProviderError(self.name, f"Stream error: {e}", retryable=True) from e

    def _build_payload(
        self, request: ModelRequest, model: str, *, stream: bool = False
    ) -> dict[str, Any]:
        """Build the Gemini API payload."""
        contents: list[dict[str, Any]] = []
        system_instruction: str | None = None

        for msg in request.messages:
            if msg.role == ModelRole.SYSTEM:
                system_instruction = (
                    msg.content if isinstance(msg.content, str) else str(msg.content)
                )
            else:
                role = "model" if msg.role == ModelRole.ASSISTANT else msg.role.value
                contents.append(
                    {
                        "role": role,
                        "parts": [
                            {
                                "text": msg.content
                                if isinstance(msg.content, str)
                                else str(msg.content)
                            }
                        ],
                    }
                )

        payload: dict[str, Any] = {
            "contents": contents,
            "generationConfig": {
                "temperature": request.temperature,
                "maxOutputTokens": request.max_tokens or 4096,
                "topP": request.top_p,
            },
        }
        if system_instruction:
            payload["systemInstruction"] = {"parts": [{"text": system_instruction}]}
        if request.stop:
            payload["generationConfig"]["stopSequences"] = request.stop
        if request.tools:
            payload["tools"] = [
                {
                    "functionDeclarations": [
                        {"name": t.name, "description": t.description, "parameters": t.parameters}
                        for t in request.tools
                    ],
                }
            ]
        return payload

    def _parse_response(
        self, data: dict[str, Any], request: ModelRequest, latency_s: float
    ) -> ModelResponse:
        """Parse the Gemini response format."""
        candidates = data.get("candidates", [])
        content = ""
        tool_calls: list[ToolCall] = []
        if candidates:
            parts = candidates[0].get("content", {}).get("parts", [])
            for part in parts:
                if "text" in part:
                    content += part["text"]
                elif "functionCall" in part:
                    fc = part["functionCall"]
                    tool_calls.append(
                        ToolCall(
                            id=fc.get("name", ""),
                            name=fc.get("name", ""),
                            arguments=fc.get("args", {}),
                        )
                    )

        usage_data = data.get("usageMetadata", {})
        usage = UsageStats(
            prompt_tokens=usage_data.get("promptTokenCount", 0),
            completion_tokens=usage_data.get("candidatesTokenCount", 0),
            total_tokens=usage_data.get("totalTokenCount", 0),
        )
        model = data.get("modelVersion", self._select_model(request))
        cost = self._calculate_cost(model, usage)

        finish_reason = "stop"
        if candidates:
            fr = candidates[0].get("finishReason", "STOP")
            if fr == "MAX_TOKENS":
                finish_reason = "length"
            elif fr == "SAFETY":
                finish_reason = "content_filter"

        return ModelResponse(
            request_id=str(request.id),
            provider=self.name,
            model=model,
            content=content,
            tool_calls=tool_calls,
            usage=usage,
            cost_usd=cost,
            latency_s=latency_s,
            finish_reason=finish_reason,
        )

    def _parse_gemini_stream_chunk(
        self,
        data: dict[str, Any],
        request_id: str,
        model: str,
    ) -> ModelStreamChunk | None:
        """Parse a Gemini stream chunk."""
        candidates = data.get("candidates", [])
        if not candidates:
            return None
        parts = candidates[0].get("content", {}).get("parts", [])
        text = "".join(p.get("text", "") for p in parts)
        finish_reason = None
        if "finishReason" in candidates[0]:
            fr = candidates[0]["finishReason"]
            finish_reason = "length" if fr == "MAX_TOKENS" else "stop"
        usage_data = data.get("usageMetadata")
        usage = None
        if usage_data:
            usage = UsageStats(
                prompt_tokens=usage_data.get("promptTokenCount", 0),
                completion_tokens=usage_data.get("candidatesTokenCount", 0),
                total_tokens=usage_data.get("totalTokenCount", 0),
            )
        return ModelStreamChunk(
            request_id=request_id,
            provider=self.name,
            model=model,
            content_delta=text,
            finish_reason=finish_reason,
            usage=usage,
        )

    async def health_check(self) -> ProviderHealth:
        """Probe Google's health by listing models."""
        if self._client is None or self._config is None:
            return ProviderHealth(
                provider=self.name,
                status=ProviderStatus.UNHEALTHY,
                last_error="not initialized",
            )
        try:
            api_key = self._config.api_key.get_secret_value() if self._config.api_key else ""
            response = await self._client.get(f"/models?key={api_key}", timeout=10.0)
            response.raise_for_status()
            return ProviderHealth(provider=self.name, status=ProviderStatus.HEALTHY)
        except Exception as e:
            return ProviderHealth(
                provider=self.name,
                status=ProviderStatus.UNHEALTHY,
                last_error=str(e),
            )
