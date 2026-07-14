"""Tests for core.config — layered loader, SecretRef, hot-reload."""

from __future__ import annotations

from pathlib import Path

import pytest

from core.config import (
    ConfigManager,
    ConfigNotFoundError,
    ConfigSource,
    ConfigValidationError,
    SecretRef,
    get_config,
    init_config,
    set_config,
)
from core.config.exceptions import ConfigLoadError


@pytest.fixture(autouse=True)
def _reset_config():
    """Reset config singleton before and after each test."""
    set_config(ConfigManager())  # type: ignore[arg-type]
    yield
    set_config(ConfigManager())  # type: ignore[arg-type]


@pytest.mark.offline
class TestSecretRef:
    """SecretRef tests."""

    def test_parse_valid_placeholder(self) -> None:
        ref = SecretRef.parse("${secret:openai/api_key}")
        assert ref is not None
        assert ref.name == "openai/api_key"

    def test_parse_invalid_returns_none(self) -> None:
        assert SecretRef.parse("not a secret") is None
        assert SecretRef.parse("${secret:}") is None  # empty name
        assert SecretRef.parse("plain text") is None
        assert SecretRef.parse(123) is None  # type: ignore[arg-type]

    def test_is_secret_ref(self) -> None:
        assert SecretRef.is_secret_ref("${secret:foo}") is True
        assert SecretRef.is_secret_ref("foo") is False

    def test_str_roundtrip(self) -> None:
        ref = SecretRef(name="foo/bar")
        assert str(ref) == "${secret:foo/bar}"
        # And we can re-parse it
        assert SecretRef.parse(str(ref)) == ref


@pytest.mark.offline
class TestConfigManager:
    """ConfigManager tests."""

    def test_load_from_yaml(self, tmp_path: Path) -> None:
        yaml_file = tmp_path / "config.yaml"
        yaml_file.write_text(
            "db:\n  url: postgresql://localhost/aaios\n  pool_size: 10\n",
            encoding="utf-8",
        )
        cm = ConfigManager()
        cm.load(yaml_path=yaml_file)
        assert cm.get("db.url") == "postgresql://localhost/aaios"
        assert cm.get("db.pool_size") == 10
        assert cm.source_of("db.url") == ConfigSource.YAML

    def test_load_from_env(self) -> None:
        cm = ConfigManager()
        cm.load(env={"AAiOS_DB_URL": "postgresql://test/aaios", "OTHER_VAR": "ignore"})
        assert cm.get("db.url") == "postgresql://test/aaios"
        assert cm.source_of("db.url") == ConfigSource.ENV
        assert not cm.has("other.var")

    def test_load_from_env_file(self, tmp_path: Path) -> None:
        env_file = tmp_path / ".env"
        env_file.write_text(
            "# comment\nAAiOS_DB_URL=postgresql://envfile/aaios\nAAiOS_DEBUG=true\n",
            encoding="utf-8",
        )
        cm = ConfigManager()
        cm.load(env_file_path=env_file)
        assert cm.get("db.url") == "postgresql://envfile/aaios"
        assert cm.get("debug") is True
        assert cm.source_of("db.url") == ConfigSource.ENV_FILE

    def test_priority_cli_overrides_everything(self, tmp_path: Path) -> None:
        yaml_file = tmp_path / "config.yaml"
        yaml_file.write_text("db:\n  url: from_yaml\n", encoding="utf-8")
        cm = ConfigManager()
        cm.load(
            yaml_path=yaml_file,
            env={"AAiOS_DB_URL": "from_env"},
            overrides={"db.url": "from_cli"},
        )
        assert cm.get("db.url") == "from_cli"
        assert cm.source_of("db.url") == ConfigSource.CLI

    def test_priority_env_over_yaml(self, tmp_path: Path) -> None:
        yaml_file = tmp_path / "config.yaml"
        yaml_file.write_text("db:\n  url: from_yaml\n", encoding="utf-8")
        cm = ConfigManager()
        cm.load(yaml_path=yaml_file, env={"AAiOS_DB_URL": "from_env"})
        assert cm.get("db.url") == "from_env"

    def test_secret_ref_parsed(self, tmp_path: Path) -> None:
        yaml_file = tmp_path / "config.yaml"
        yaml_file.write_text(
            "providers:\n  openai:\n    api_key: ${secret:openai/api_key}\n",
            encoding="utf-8",
        )
        cm = ConfigManager()
        cm.load(yaml_path=yaml_file)
        ref = cm.get_secret_ref("providers.openai.api_key")
        assert ref is not None
        assert ref.name == "openai/api_key"

    def test_get_with_default(self) -> None:
        cm = ConfigManager()
        assert cm.get("missing.key", "fallback") == "fallback"

    def test_get_raises_when_no_default(self) -> None:
        cm = ConfigManager()
        with pytest.raises(ConfigNotFoundError):
            cm.get("missing.key")

    def test_get_typed_validates(self) -> None:
        cm = ConfigManager()
        cm.load(overrides={"port": 8080})
        assert cm.get_typed("port", int) == 8080
        with pytest.raises(ConfigValidationError):
            cm.get_typed("port", str)

    def test_get_str_int_float_bool(self) -> None:
        cm = ConfigManager()
        cm.load(
            overrides={
                "s": "hello",
                "i": 42,
                "f": 3.14,
                "b": True,
            }
        )
        assert cm.get_str("s") == "hello"
        assert cm.get_int("i") == 42
        assert cm.get_float("f") == 3.14
        assert cm.get_bool("b") is True

    def test_list_keys_with_prefix(self) -> None:
        cm = ConfigManager()
        cm.load(
            overrides={
                "db.url": "x",
                "db.pool": 1,
                "web.port": 8080,
            }
        )
        db_keys = cm.list_keys("db.")
        assert "db.url" in db_keys
        assert "db.pool" in db_keys
        assert "web.port" not in db_keys

    def test_set_updates_value_and_notifies(self) -> None:
        cm = ConfigManager()
        cm.load(overrides={"port": 8080})
        notified: list[str] = []
        cm.watch("port", lambda keys: notified.extend(keys))
        cm.set("port", 9090)
        assert cm.get("port") == 9090
        assert notified == ["port"]

    def test_yaml_parse_error_raises(self, tmp_path: Path) -> None:
        bad_yaml = tmp_path / "bad.yaml"
        bad_yaml.write_text("db:\n  url: [unclosed\n", encoding="utf-8")
        cm = ConfigManager()
        with pytest.raises(ConfigLoadError):
            cm.load(yaml_path=bad_yaml)

    def test_init_config_singleton(self) -> None:
        cm = init_config(overrides={"foo": "bar"})
        assert get_config() is cm
        assert get_config().get("foo") == "bar"


@pytest.mark.offline
class TestSecretRefIntegration:
    """SecretRef integration with the config manager."""

    def test_secret_ref_in_complex_yaml(self, tmp_path: Path) -> None:
        yaml_file = tmp_path / "config.yaml"
        yaml_file.write_text(
            """
providers:
  openai:
    api_key: ${secret:openai/api_key}
    org: my-org
  anthropic:
    api_key: ${secret:anthropic/api_key}
""",
            encoding="utf-8",
        )
        cm = ConfigManager()
        cm.load(yaml_path=yaml_file)
        assert cm.get_secret_ref("providers.openai.api_key") is not None
        assert cm.get("providers.openai.org") == "my-org"
        assert cm.get_secret_ref("providers.anthropic.api_key") is not None
