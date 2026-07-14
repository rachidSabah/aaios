"""LM Studio provider — local OpenAI-compatible server."""

from __future__ import annotations

from core.contracts.provider import ModelInfo, ProviderType
from services.model_router.providers.openai_compatible import OpenAICompatibleProvider


class LMStudioProvider(OpenAICompatibleProvider):
    """LM Studio provider — local models via LM Studio's OpenAI-compatible server.

    No API key required (local). Models are whatever the user has loaded in LM Studio.
    """

    _provider_type = ProviderType.LM_STUDIO
    _default_base_url = "http://localhost:1234/v1"

    _model_catalog: dict[str, ModelInfo] = {}
    # Models are discovered at runtime via the /models endpoint
