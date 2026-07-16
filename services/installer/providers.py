"""Phase 6 — Provider Configuration.

Discovers, validates, and configures every supported LLM provider:

  OpenAI, Anthropic, Google AI, OpenRouter, DeepSeek, GLM, NVIDIA, Groq,
  Mistral, Azure OpenAI, Ollama, LM Studio, and custom OpenAI-compatible APIs.

Each provider is validated before being enabled. Failing providers are
disabled automatically while the installation continues.
"""

from __future__ import annotations

import os
import time
from typing import Any

from core.logging import get_logger
from services.installer.models import ProviderCheck

_log = get_logger(__name__)

__all__ = ["ProviderConfigurator", "SUPPORTED_PROVIDERS"]


SUPPORTED_PROVIDERS: tuple[str, ...] = (
    "openai",
    "anthropic",
    "google",
    "openrouter",
    "deepseek",
    "glm",
    "nvidia",
    "groq",
    "mistral",
    "azure_openai",
    "ollama",
    "lm_studio",
    "custom",
)


# Per-provider configuration metadata
_PROVIDER_META: dict[str, dict[str, Any]] = {
    "openai": {
        "env_var": "OPENAI_API_KEY",
        "base_url": "https://api.openai.com/v1",
        "supports_streaming": True,
        "supports_tools": True,
        "supports_vision": True,
        "supports_reasoning": True,
        "default_models": ["gpt-4o", "gpt-4o-mini", "o1", "o3-mini"],
    },
    "anthropic": {
        "env_var": "ANTHROPIC_API_KEY",
        "base_url": "https://api.anthropic.com",
        "supports_streaming": True,
        "supports_tools": True,
        "supports_vision": True,
        "supports_reasoning": True,
        "default_models": ["claude-3-5-sonnet", "claude-3-5-haiku", "claude-3-opus"],
    },
    "google": {
        "env_var": "GOOGLE_API_KEY",
        "base_url": "https://generativelanguage.googleapis.com",
        "supports_streaming": True,
        "supports_tools": True,
        "supports_vision": True,
        "supports_reasoning": True,
        "default_models": ["gemini-2.0-flash", "gemini-2.0-pro", "gemini-1.5-pro"],
    },
    "openrouter": {
        "env_var": "OPENROUTER_API_KEY",
        "base_url": "https://openrouter.ai/api/v1",
        "supports_streaming": True,
        "supports_tools": True,
        "supports_vision": True,
        "supports_reasoning": True,
        "default_models": [],
    },
    "deepseek": {
        "env_var": "DEEPSEEK_API_KEY",
        "base_url": "https://api.deepseek.com/v1",
        "supports_streaming": True,
        "supports_tools": True,
        "supports_vision": False,
        "supports_reasoning": True,
        "default_models": ["deepseek-chat", "deepseek-reasoner"],
    },
    "glm": {
        "env_var": "GLM_API_KEY",
        "base_url": "https://open.bigmodel.cn/api/paas/v4",
        "supports_streaming": True,
        "supports_tools": True,
        "supports_vision": True,
        "supports_reasoning": True,
        "default_models": ["glm-4-plus", "glm-4-air", "glm-4-flash"],
    },
    "nvidia": {
        "env_var": "NVIDIA_API_KEY",
        "base_url": "https://integrate.api.nvidia.com/v1",
        "supports_streaming": True,
        "supports_tools": True,
        "supports_vision": True,
        "supports_reasoning": True,
        "default_models": [],
    },
    "groq": {
        "env_var": "GROQ_API_KEY",
        "base_url": "https://api.groq.com/openai/v1",
        "supports_streaming": True,
        "supports_tools": True,
        "supports_vision": False,
        "supports_reasoning": True,
        "default_models": ["llama-3.3-70b", "mixtral-8x7b"],
    },
    "mistral": {
        "env_var": "MISTRAL_API_KEY",
        "base_url": "https://api.mistral.ai/v1",
        "supports_streaming": True,
        "supports_tools": True,
        "supports_vision": False,
        "supports_reasoning": True,
        "default_models": ["mistral-large", "mistral-small", "codestral"],
    },
    "azure_openai": {
        "env_var": "AZURE_OPENAI_API_KEY",
        "base_url": "",  # must be set explicitly
        "supports_streaming": True,
        "supports_tools": True,
        "supports_vision": True,
        "supports_reasoning": True,
        "default_models": [],
    },
    "ollama": {
        "env_var": "",  # local, no API key needed
        "base_url": "http://127.0.0.1:11434",
        "supports_streaming": True,
        "supports_tools": False,
        "supports_vision": False,
        "supports_reasoning": False,
        "default_models": ["llama3.2", "qwen2.5", "deepseek-r1"],
    },
    "lm_studio": {
        "env_var": "",
        "base_url": "http://127.0.0.1:1234/v1",
        "supports_streaming": True,
        "supports_tools": False,
        "supports_vision": False,
        "supports_reasoning": False,
        "default_models": [],
    },
    "custom": {
        "env_var": "CUSTOM_API_KEY",
        "base_url": "",  # must be set explicitly
        "supports_streaming": True,
        "supports_tools": True,
        "supports_vision": False,
        "supports_reasoning": False,
        "default_models": [],
    },
}


class ProviderConfigurator:
    """Phase 6 — discover, validate, and configure LLM providers.

    The configurator is read-only with respect to the network: it never
    makes real LLM calls. Validation checks for:
      - API key presence (when required)
      - Base URL reachability (best-effort, optional)
      - Configuration completeness
    """

    def __init__(self, workspace_root: str = "") -> None:
        self._workspace_root = workspace_root

    def discover_all(self) -> list[ProviderCheck]:
        """Discover and validate every supported provider."""
        results: list[ProviderCheck] = []
        for name in SUPPORTED_PROVIDERS:
            results.append(self._check_one(name))
        return results

    def discover_local(self) -> list[ProviderCheck]:
        """Discover only local providers (Ollama, LM Studio)."""
        return [self._check_one(n) for n in ("ollama", "lm_studio")]

    def discover_cloud(self) -> list[ProviderCheck]:
        """Discover only cloud providers (everything except local)."""
        return [
            self._check_one(n) for n in SUPPORTED_PROVIDERS
            if n not in ("ollama", "lm_studio")
        ]

    def configure_provider(
        self,
        name: str,
        *,
        api_key: str = "",
        base_url: str = "",
        proxy_url: str = "",
        region: str = "",
        rate_limit_per_minute: int = 60,
        fallback_priority: int = 0,
    ) -> ProviderCheck:
        """Configure a single provider with explicit settings."""
        meta = _PROVIDER_META.get(name)
        if not meta:
            return ProviderCheck(
                name=name,
                configured=False,
                error=f"Unknown provider: {name}",
            )
        # Validate
        check = ProviderCheck(
            name=name,
            configured=True,
            enabled=True,
            supports_streaming=meta["supports_streaming"],
            supports_tools=meta["supports_tools"],
            supports_vision=meta["supports_vision"],
            supports_reasoning=meta["supports_reasoning"],
            fallback_priority=fallback_priority,
            models_discovered=list(meta["default_models"]),
        )
        # If an API key is required and not provided, mark as not healthy
        env_var = meta["env_var"]
        if env_var and not api_key and not os.environ.get(env_var):
            check.healthy = False
            check.enabled = False
            check.error = f"missing API key (set {env_var} or pass api_key)"
        elif env_var and (api_key or os.environ.get(env_var)):
            check.healthy = True
        else:
            # Local provider — no key required
            check.healthy = True
        # Save the configuration to the workspace
        self._save_provider_config(name, {
            "api_key_set": bool(api_key or os.environ.get(env_var, "")),
            "base_url": base_url or meta["base_url"],
            "proxy_url": proxy_url,
            "region": region,
            "rate_limit_per_minute": rate_limit_per_minute,
            "fallback_priority": fallback_priority,
            "enabled": check.enabled,
            "healthy": check.healthy,
        })
        return check

    def validate_provider(self, name: str) -> ProviderCheck:
        """Validate an already-configured provider."""
        config = self._load_provider_config(name)
        if not config:
            return ProviderCheck(
                name=name,
                configured=False,
                error="not configured",
            )
        # Check connectivity (best-effort)
        start = time.monotonic()
        latency_ms = 0.0
        healthy = True
        error: str | None = None
        try:
            import socket
            from urllib.parse import urlparse
            url = config.get("base_url", "")
            if url:
                parsed = urlparse(url)
                host = parsed.hostname or "127.0.0.1"
                port = parsed.port or (443 if parsed.scheme == "https" else 80)
                sock = socket.create_connection((host, port), timeout=3)
                sock.close()
                latency_ms = (time.monotonic() - start) * 1000
        except OSError as e:
            healthy = False
            error = f"connection failed: {e}"
        return ProviderCheck(
            name=name,
            configured=True,
            enabled=config.get("enabled", False),
            healthy=healthy,
            error=error,
            health_check_latency_ms=round(latency_ms, 2),
        )

    def list_supported(self) -> list[dict[str, Any]]:
        """List all supported providers with their metadata."""
        return [
            {"name": name, **meta}
            for name, meta in _PROVIDER_META.items()
        ]

    def disable_provider(self, name: str) -> bool:
        """Disable a provider (e.g. after a failed health check)."""
        config = self._load_provider_config(name)
        if not config:
            return False
        config["enabled"] = False
        config["healthy"] = False
        self._save_provider_config(name, config)
        return True

    def configure_fallback_routing(
        self, priorities: dict[str, int]
    ) -> dict[str, int]:
        """Configure fallback routing across providers.

        Args:
            priorities: mapping of provider name → priority (lower = higher priority).

        Returns:
            The applied priorities.
        """
        applied: dict[str, int] = {}
        for name, priority in priorities.items():
            config = self._load_provider_config(name)
            if config:
                config["fallback_priority"] = priority
                self._save_provider_config(name, config)
                applied[name] = priority
        return applied

    # --- helpers --------------------------------------------------------

    def _check_one(self, name: str) -> ProviderCheck:
        """Check a single provider's configuration status."""
        meta = _PROVIDER_META.get(name)
        if not meta:
            return ProviderCheck(name=name, error=f"unknown provider: {name}")
        # Load existing config if any
        config = self._load_provider_config(name)
        env_var = meta["env_var"]
        api_key_present = bool(
            (config and config.get("api_key_set"))
            or (env_var and os.environ.get(env_var))
        )
        configured = bool(config)
        enabled = bool(config and config.get("enabled")) if configured else False
        # Auto-enable local providers if their service is reachable
        if name in ("ollama", "lm_studio") and not configured:
            try:
                import socket
                from urllib.parse import urlparse
                url = meta["base_url"]
                parsed = urlparse(url)
                host = parsed.hostname or "127.0.0.1"
                port = parsed.port or 80
                sock = socket.create_connection((host, port), timeout=1)
                sock.close()
                configured = True
                enabled = True
            except OSError:
                pass
        return ProviderCheck(
            name=name,
            configured=configured,
            enabled=enabled,
            healthy=enabled and (api_key_present or not env_var),
            models_discovered=list(meta["default_models"]),
            supports_streaming=meta["supports_streaming"],
            supports_tools=meta["supports_tools"],
            supports_vision=meta["supports_vision"],
            supports_reasoning=meta["supports_reasoning"],
            fallback_priority=(config or {}).get("fallback_priority", 0),
            error=None if (configured or not env_var) else f"set {env_var} to enable",
        )

    def _provider_config_path(self, name: str) -> str:
        from pathlib import Path
        if not self._workspace_root:
            return ""
        return str(Path(self._workspace_root) / "providers" / f"{name}.json")

    def _save_provider_config(self, name: str, config: dict[str, Any]) -> None:
        import json
        from pathlib import Path
        if not self._workspace_root:
            return
        path = Path(self._workspace_root) / "providers" / f"{name}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        # Never write the actual API key
        safe_config = {k: v for k, v in config.items() if k != "api_key"}
        path.write_text(json.dumps(safe_config, indent=2, default=str))

    def _load_provider_config(self, name: str) -> dict[str, Any] | None:
        import json
        from pathlib import Path
        if not self._workspace_root:
            return None
        path = Path(self._workspace_root) / "providers" / f"{name}.json"
        if not path.exists():
            return None
        try:
            return dict(json.loads(path.read_text()))
        except (json.JSONDecodeError, OSError):
            return None
