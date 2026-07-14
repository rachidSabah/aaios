"""Groq provider — ultra-fast inference, OpenAI-compatible."""

from __future__ import annotations

from core.contracts.provider import ModelInfo, ProviderType
from services.model_router.providers.openai_compatible import OpenAICompatibleProvider


class GroqProvider(OpenAICompatibleProvider):
    """Groq provider — fast inference for open models."""

    _provider_type = ProviderType.GROQ
    _default_base_url = "https://api.groq.com/openai/v1"

    _model_catalog: dict[str, ModelInfo] = {
        "llama-3.3-70b-versatile": ModelInfo(
            name="llama-3.3-70b-versatile",
            display_name="Llama 3.3 70B (Groq)",
            provider="groq",
            supports_tools=True,
            context_window=128_000,
            max_output_tokens=8_192,
            cost_per_1m_input_usd=0.59,
            cost_per_1m_output_usd=0.79,
        ),
        "llama-3.1-8b-instant": ModelInfo(
            name="llama-3.1-8b-instant",
            display_name="Llama 3.1 8B Instant (Groq)",
            provider="groq",
            supports_tools=True,
            context_window=128_000,
            max_output_tokens=8_192,
            cost_per_1m_input_usd=0.05,
            cost_per_1m_output_usd=0.08,
        ),
    }
