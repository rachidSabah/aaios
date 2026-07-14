"""Provider adapters — 13 providers.

10 are OpenAI-compatible (share OpenAICompatibleProvider base):
  OpenAI, Azure OpenAI, OpenRouter, DeepSeek, GLM, NVIDIA, Groq, Mistral,
  LM Studio, Custom

3 have their own API format:
  Anthropic (Messages API), Google (Gemini API), Ollama (uses OpenAI-compat endpoint)
"""

from __future__ import annotations

from services.model_router.providers.anthropic_provider import AnthropicProvider
from services.model_router.providers.azure_openai_provider import AzureOpenAIProvider
from services.model_router.providers.custom_provider import CustomProvider
from services.model_router.providers.deepseek_provider import DeepSeekProvider
from services.model_router.providers.glm_provider import GLMProvider
from services.model_router.providers.google_provider import GoogleProvider
from services.model_router.providers.groq_provider import GroqProvider
from services.model_router.providers.lm_studio_provider import LMStudioProvider
from services.model_router.providers.mistral_provider import MistralProvider
from services.model_router.providers.nvidia_provider import NVIDIAProvider
from services.model_router.providers.ollama_provider import OllamaProvider
from services.model_router.providers.openai_compatible import OpenAICompatibleProvider
from services.model_router.providers.openai_provider import OpenAIProvider
from services.model_router.providers.openrouter_provider import OpenRouterProvider

__all__ = [
    "AnthropicProvider",
    "AzureOpenAIProvider",
    "CustomProvider",
    "DeepSeekProvider",
    "GLMProvider",
    "GoogleProvider",
    "GroqProvider",
    "LMStudioProvider",
    "MistralProvider",
    "NVIDIAProvider",
    "OllamaProvider",
    "OpenAICompatibleProvider",
    "OpenAIProvider",
    "OpenRouterProvider",
]
