"""Configuration system exceptions."""

from __future__ import annotations


class ConfigError(Exception):
    """Base class for configuration errors."""


class ConfigValidationError(ConfigError):
    """Raised when a config value fails schema validation."""

    def __init__(self, key: str, value: object, reason: str) -> None:
        super().__init__(f"Config key '{key}' (value={value!r}): {reason}")
        self.key = key
        self.value = value
        self.reason = reason


class ConfigNotFoundError(ConfigError):
    """Raised when a config key is not found and has no default."""

    def __init__(self, key: str) -> None:
        super().__init__(f"Config key '{key}' not found and has no default.")
        self.key = key


class ConfigLoadError(ConfigError):
    """Raised when a config source cannot be loaded (file missing, parse error)."""

    def __init__(self, source: str, reason: str) -> None:
        super().__init__(f"Failed to load config from {source}: {reason}")
        self.source = source
        self.reason = reason
