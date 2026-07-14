"""The Config Manager — layered loader, schema validation, hot-reload.

Load order (highest priority first):
    1. CLI overrides (passed to ``load()`` as ``overrides`` dict)
    2. Environment variables (``AAiOS_<SECTION>_<KEY>`` → ``section.key``)
    3. .env file (parsed as KEY=VALUE, same env-var naming)
    4. config.yaml (the user's main config)
    5. Built-in defaults (config/defaults.yaml)

Hot-reload: the file watcher checks the config file mtime every N seconds
(default 5). On change, the file is re-loaded, the diff is computed, and
``config.changed`` events are emitted for each changed key. Subscribers
(e.g. the Model Router) react accordingly.

Secrets: values matching ``${secret:name}`` are parsed into ``SecretRef``
instances at load time and never resolved by the kernel. The kernel stores
them as opaque references; resolution happens in the Security Layer.
"""

from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any, TypeVar

import yaml
from pydantic import BaseModel, Field

from core.config.exceptions import ConfigLoadError, ConfigNotFoundError
from core.config.secret_ref import SecretRef
from core.logging import get_logger

_log = get_logger(__name__)

# Env var prefix — AAiOS_DB_URL → db.url, AAiOS_PROVIDERS_OPENAI_API_KEY → providers.openai.api_key
_ENV_PREFIX = "AAiOS_"

# TypeVar for the typed config getter
T = TypeVar("T")


class ConfigSource(StrEnum):
    """Where a config value came from — for debugging and audit."""

    CLI = "cli"
    ENV = "env"
    ENV_FILE = "env_file"
    YAML = "yaml"
    DEFAULTS = "defaults"


class ConfigValue(BaseModel):
    """A config value with provenance."""

    value: Any
    source: ConfigSource
    source_detail: str = Field(default="", description="e.g. file path or env var name.")


@dataclass
class _Subscriber:
    """A callback registered via ``watch()``."""

    key_prefix: str
    callback: Any  # callable[[list[str]], Awaitable[None]] | callable[[list[str]], None]
    call_soon: bool = False  # if True, callback is sync


class ConfigManager:
    """The singleton-ish config manager.

    Use ``init_config()`` to create one and ``get_config()`` to retrieve it.
    Components should call ``get_config().get(key)`` rather than holding a
    long-lived reference — this allows hot-reload to take effect.
    """

    def __init__(self) -> None:
        self._values: dict[str, ConfigValue] = {}
        self._subscribers: list[_Subscriber] = []
        self._watchers: list[asyncio.Task[None]] = []
        self._yaml_path: Path | None = None
        self._env_file_path: Path | None = None
        self._defaults_path: Path | None = None
        self._log = _log

    # ------------------------------------------------------------------
    # Loading
    # ------------------------------------------------------------------

    def load(
        self,
        *,
        yaml_path: Path | None = None,
        env_file_path: Path | None = None,
        defaults_path: Path | None = None,
        overrides: dict[str, Any] | None = None,
        env: dict[str, str] | None = None,
    ) -> None:
        """Load config from all sources, in priority order.

        Args:
            yaml_path: path to config.yaml (user's main config).
            env_file_path: path to .env file.
            defaults_path: path to defaults.yaml (bundled with AAiOS).
            overrides: programmatic overrides (highest priority).
            env: environment variables to use (defaults to os.environ).
        """
        env = env if env is not None else dict(os.environ)
        self._defaults_path = defaults_path
        self._yaml_path = yaml_path
        self._env_file_path = env_file_path

        # Reset and load in reverse priority order (lowest first)
        self._values.clear()

        # 5. Defaults
        if defaults_path is not None and defaults_path.is_file():
            self._load_yaml(defaults_path, ConfigSource.DEFAULTS)

        # 4. YAML (user config)
        if yaml_path is not None and yaml_path.is_file():
            self._load_yaml(yaml_path, ConfigSource.YAML)

        # 3. .env file
        if env_file_path is not None and env_file_path.is_file():
            self._load_env_file(env_file_path)

        # 2. Environment variables
        self._load_env(env)

        # 1. CLI overrides
        if overrides:
            for k, v in overrides.items():
                self._set(k, v, ConfigSource.CLI, "cli override")

        self._log.info(
            "config.loaded",
            total_keys=len(self._values),
            yaml_path=str(yaml_path) if yaml_path else None,
            env_file=str(env_file_path) if env_file_path else None,
            defaults=str(defaults_path) if defaults_path else None,
        )

    def _load_yaml(self, path: Path, source: ConfigSource) -> None:
        """Load a YAML file into ``_values``."""
        try:
            with path.open("r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
        except yaml.YAMLError as e:
            raise ConfigLoadError(str(path), f"YAML parse error: {e}") from e
        self._flatten_into(data, prefix="", source=source, source_detail=str(path))

    def _load_env_file(self, path: Path) -> None:
        """Load a .env file (KEY=VALUE lines, # comments, no quoting complexity)."""
        with path.open("r", encoding="utf-8") as f:
            for line_no, raw_line in enumerate(f, start=1):
                stripped = raw_line.strip()
                if not stripped or stripped.startswith("#"):
                    continue
                if "=" not in stripped:
                    continue
                key, _, value = stripped.partition("=")
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                # Convert AAiOS_FOO_BAR → foo.bar
                if key.startswith(_ENV_PREFIX):
                    dotted = key[len(_ENV_PREFIX) :].lower().replace("_", ".")
                    self._set(
                        dotted, self._parse_value(value), ConfigSource.ENV_FILE, f"{path}:{line_no}"
                    )

    def _load_env(self, env: dict[str, str]) -> None:
        """Load from environment variables (``AAiOS_FOO_BAR`` → ``foo.bar``)."""
        for key, value in env.items():
            if not key.startswith(_ENV_PREFIX):
                continue
            dotted = key[len(_ENV_PREFIX) :].lower().replace("_", ".")
            self._set(dotted, self._parse_value(value), ConfigSource.ENV, key)

    def _flatten_into(
        self,
        data: dict[str, Any],
        prefix: str,
        source: ConfigSource,
        source_detail: str,
    ) -> None:
        """Recursively flatten a nested dict into dotted keys."""
        for key, value in data.items():
            full_key = f"{prefix}.{key}" if prefix else key
            if isinstance(value, dict):
                self._flatten_into(value, full_key, source, source_detail)
            else:
                self._set(full_key, self._parse_value(value), source, source_detail)

    def _parse_value(self, value: Any) -> Any:
        """Parse a raw config value.

        - ``${secret:name}`` → ``SecretRef(name)``
        - Strings that look like ints/floats/bools → those types
        - Everything else → as-is
        """
        if isinstance(value, str):
            ref = SecretRef.parse(value)
            if ref is not None:
                return ref
            # Best-effort type coercion for env vars
            lower = value.lower()
            if lower in ("true", "false"):
                return lower == "true"
            if lower in ("null", "none", "~"):
                return None
            try:
                if "." in value:
                    return float(value)
                return int(value)
            except ValueError:
                return value
        return value

    def _set(
        self,
        key: str,
        value: Any,
        source: ConfigSource,
        source_detail: str = "",
    ) -> None:
        """Set a config value (does not emit change events)."""
        self._values[key] = ConfigValue(value=value, source=source, source_detail=source_detail)

    # ------------------------------------------------------------------
    # Access
    # ------------------------------------------------------------------

    def get(
        self,
        key: str,
        default: Any = ...,
    ) -> Any:
        """Return the config value at ``key``.

        Args:
            key: dotted path, e.g. ``db.url``.
            default: value to return if not found. If not provided and the
                key is missing, raises ``ConfigNotFoundError``.
        """
        if key not in self._values:
            if default is ...:
                raise ConfigNotFoundError(key)
            return default
        return self._values[key].value

    def get_typed(self, key: str, expected_type: type[T], default: Any = ...) -> T:
        """Return the config value at ``key``, asserting its type."""
        value = self.get(key, default)
        if value is default:
            return default  # type: ignore[no-any-return]
        if not isinstance(value, expected_type):
            from core.config.exceptions import ConfigValidationError

            raise ConfigValidationError(
                key,
                value,
                f"expected {expected_type.__name__}, got {type(value).__name__}",
            )
        return value

    def get_str(self, key: str, default: str | None = None) -> str | None:
        """Return a string config value."""
        value: str | None = self.get_typed(key, str, default)
        if value is default:
            return default
        return str(value)

    def get_int(self, key: str, default: int | None = None) -> int | None:
        """Return an int config value."""
        value: int | None = self.get_typed(key, int, default)
        if value is default:
            return default
        return value

    def get_float(self, key: str, default: float | None = None) -> float | None:
        """Return a float config value."""
        value: object = self.get(key, default)
        if value is default:
            return default
        if not isinstance(value, (int, float)):
            from core.config.exceptions import ConfigValidationError

            raise ConfigValidationError(
                key,
                value,
                f"expected int or float, got {type(value).__name__}",
            )
        return float(value)

    def get_bool(self, key: str, default: bool | None = None) -> bool | None:
        """Return a bool config value."""
        value = self.get_typed(key, bool, default)
        if value is default:
            return default
        return bool(value)

    def get_secret_ref(self, key: str) -> SecretRef | None:
        """Return a SecretRef if the value at ``key`` is a secret reference."""
        if key not in self._values:
            return None
        value = self._values[key].value
        return value if isinstance(value, SecretRef) else None

    def has(self, key: str) -> bool:
        """Return True if ``key`` exists in the config."""
        return key in self._values

    def list_keys(self, prefix: str = "") -> list[str]:
        """Return all keys (optionally under ``prefix``)."""
        if not prefix:
            return sorted(self._values.keys())
        return sorted(k for k in self._values if k.startswith(prefix))

    def source_of(self, key: str) -> ConfigSource | None:
        """Return where a config value came from, or None if not found."""
        if key not in self._values:
            return None
        return self._values[key].source

    # ------------------------------------------------------------------
    # Hot-reload
    # ------------------------------------------------------------------

    def set(self, key: str, value: Any) -> None:
        """Programmatically set a config value and emit a change event."""
        old = self._values.get(key)
        self._set(key, self._parse_value(value), ConfigSource.CLI, "set()")
        if old is None or old.value != value:
            self._notify_subscribers([key])

    async def watch_file(self, path: Path, interval_s: float = 5.0) -> None:
        """Watch ``path`` for changes and reload on mtime change.

        Run as an asyncio task. Cancel to stop watching.
        """
        last_mtime = path.stat().st_mtime if path.is_file() else 0.0
        while True:
            await asyncio.sleep(interval_s)
            try:
                current_mtime = path.stat().st_mtime if path.is_file() else 0.0
            except OSError:
                continue
            if current_mtime <= last_mtime:
                continue
            last_mtime = current_mtime
            self._log.info("config.file_changed", path=str(path))
            old_keys = dict(self._values)
            # Re-load everything (the YAML may have changed, and the merge
            # order must be preserved).
            self.load(
                yaml_path=self._yaml_path,
                env_file_path=self._env_file_path,
                defaults_path=self._defaults_path,
            )
            changed = [
                k
                for k, v in self._values.items()
                if k not in old_keys or old_keys[k].value != v.value
            ]
            if changed:
                self._notify_subscribers(changed)

    def start_watching(self, path: Path, interval_s: float = 5.0) -> asyncio.Task[None]:
        """Start watching ``path`` in the background. Returns the task."""
        task = asyncio.create_task(self.watch_file(path, interval_s), name=f"config.watch:{path}")
        self._watchers.append(task)
        return task

    async def stop_watching(self) -> None:
        """Stop all file watchers."""
        for task in self._watchers:
            task.cancel()
        for task in self._watchers:
            try:
                await task
            except asyncio.CancelledError:
                pass
        self._watchers.clear()

    # ------------------------------------------------------------------
    # Subscribers
    # ------------------------------------------------------------------

    def watch(self, key_prefix: str, callback: Any) -> None:
        """Register a callback for changes to keys under ``key_prefix``.

        The callback receives a list of changed keys. May be sync or async.
        """
        self._subscribers.append(
            _Subscriber(
                key_prefix=key_prefix,
                callback=callback,
                call_soon=asyncio.iscoroutinefunction(callback) is False,
            ),
        )

    def _notify_subscribers(self, changed_keys: list[str]) -> None:
        """Notify subscribers whose prefix matches any changed key."""
        for sub in self._subscribers:
            relevant = [k for k in changed_keys if k.startswith(sub.key_prefix)]
            if not relevant:
                continue
            try:
                result = sub.callback(relevant)
                if asyncio.iscoroutine(result):
                    # Schedule it; we may be in a sync context
                    try:
                        loop = asyncio.get_running_loop()
                        loop.create_task(result)
                    except RuntimeError:
                        # No running loop — close the coroutine to avoid warnings
                        result.close()
            except Exception:
                self._log.exception("config.subscriber_failed", prefix=sub.key_prefix)


# ---------------------------------------------------------------------------
# Singleton accessor
# ---------------------------------------------------------------------------

_INSTANCE: ConfigManager | None = None


def init_config(
    *,
    yaml_path: Path | None = None,
    env_file_path: Path | None = None,
    defaults_path: Path | None = None,
    overrides: dict[str, Any] | None = None,
) -> ConfigManager:
    """Initialize and load the global ConfigManager."""
    global _INSTANCE
    _INSTANCE = ConfigManager()
    _INSTANCE.load(
        yaml_path=yaml_path,
        env_file_path=env_file_path,
        defaults_path=defaults_path,
        overrides=overrides,
    )
    return _INSTANCE


def get_config() -> ConfigManager:
    """Return the global ConfigManager.

    Raises if ``init_config()`` hasn't been called.
    """
    if _INSTANCE is None:
        raise RuntimeError("ConfigManager not initialized. Call init_config() first.")
    return _INSTANCE


def set_config(manager: ConfigManager) -> None:
    """Set the global ConfigManager (for testing)."""
    global _INSTANCE
    _INSTANCE = manager
