"""Configuration Manager — layered loader, schema validation, hot-reload.

Load order (highest priority first):
    1. CLI flags (passed imperatively to ``load()``)
    2. Environment variables (``AAiOS_<SECTION>_<KEY>``)
    3. .env file (if present)
    4. config.yaml (the user's main config)
    5. Built-in defaults (config/defaults.yaml)

Every config key has a schema, a default, and a doc string. Hot-reloadable —
changes emit ``config.changed`` on the event bus. Secrets are referenced via
``${secret:name}`` placeholders and resolved at access time (never cached).

This Phase 3 implementation:
  - Implements the layered loader + schema validation + hot-reload.
  - Supports SecretRef placeholders, but the actual Secret Store is in
    services/security/ (Phase 8). Until then, unresolved SecretRefs are
    returned as opaque strings — the kernel doesn't try to decrypt them.
"""

from __future__ import annotations

from core.config.exceptions import (
    ConfigError,
    ConfigLoadError,
    ConfigNotFoundError,
    ConfigValidationError,
)
from core.config.manager import (
    ConfigManager,
    ConfigSource,
    ConfigValue,
    get_config,
    init_config,
    set_config,
)
from core.config.secret_ref import SecretRef

__all__ = [
    "ConfigError",
    "ConfigLoadError",
    "ConfigManager",
    "ConfigNotFoundError",
    "ConfigSource",
    "ConfigValidationError",
    "ConfigValue",
    "SecretRef",
    "get_config",
    "init_config",
    "set_config",
]
