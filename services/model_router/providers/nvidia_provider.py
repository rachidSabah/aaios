"""NVIDIA NIM provider — OpenAI-compatible."""

from __future__ import annotations

from core.contracts.provider import ModelInfo, ProviderType
from services.model_router.providers.openai_compatible import OpenAICompatibleProvider


class NVIDIAProvider(OpenAICompatibleProvider):
    """NVIDIA NIM provider."""

    _provider_type = ProviderType.NVIDIA
    _default_base_url = "https://integrate.api.nvidia.com/v1"

    _model_catalog: dict[str, ModelInfo] = {
        "nvidia/llama-3.1-nemotron-70b-instruct": ModelInfo(
            name="nvidia/llama-3.1-nemotron-70b-instruct",
            display_name="Llama 3.1 Nemotron 70B",
            provider="nvidia",
            supports_tools=True,
            context_window=128_000,
            max_output_tokens=4_096,
            cost_per_1m_input_usd=0.12,
            cost_per_1m_output_usd=0.30,
        ),
    }
