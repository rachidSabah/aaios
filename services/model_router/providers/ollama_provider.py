"""Ollama provider — local OpenAI-compatible server."""

from __future__ import annotations

from core.contracts.provider import ModelInfo, ProviderType
from services.model_router.providers.openai_compatible import OpenAICompatibleProvider


class OllamaProvider(OpenAICompatibleProvider):
    """Ollama provider — local models via Ollama's OpenAI-compatible endpoint.

    No API key required (local). Models are whatever the user has pulled via ``ollama pull``.
    """

    _provider_type = ProviderType.OLLAMA
    _default_base_url = "http://localhost:11434/v1"

    _model_catalog: dict[str, ModelInfo] = {
        "llama3.2": ModelInfo(
            name="llama3.2",
            display_name="Llama 3.2 (Ollama)",
            provider="ollama",
            supports_tools=True,
            context_window=128_000,
            max_output_tokens=4_096,
            cost_per_1m_input_usd=0.0,
            cost_per_1m_output_usd=0.0,
        ),
        "qwen2.5:32b": ModelInfo(
            name="qwen2.5:32b",
            display_name="Qwen 2.5 32B (Ollama)",
            provider="ollama",
            supports_tools=True,
            context_window=128_000,
            max_output_tokens=4_096,
            cost_per_1m_input_usd=0.0,
            cost_per_1m_output_usd=0.0,
        ),
    }
    # Additional models are discovered at runtime via the /models endpoint
