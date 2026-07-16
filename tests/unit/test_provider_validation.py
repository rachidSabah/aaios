"""Tests for the Provider Validation Service."""

from __future__ import annotations

import asyncio

import pytest
from pydantic import SecretStr

from core.contracts.provider import ProviderConfig, ProviderType
from services.provider_validation import (
    ProviderValidator,
    ValidationReport,
    ValidationResult,
    ValidationStatus,
)


def _make_config(
    ptype: ProviderType = ProviderType.OPENAI,
    name: str = "test",
    api_key: str | None = "sk-test",
    enabled: bool = True,
    models: list[str] | None = None,
) -> ProviderConfig:
    return ProviderConfig(
        type=ptype,
        name=name,
        enabled=enabled,
        api_key=SecretStr(api_key) if api_key else None,
        models=models,
        timeout_s=5.0,
    )


class _MockProvider:
    """Mock provider for testing — returns a configurable response."""

    def __init__(
        self,
        config: ProviderConfig,
        *,
        response: str = "pong",
        error: Exception | None = None,
        delay_s: float = 0.0,
    ) -> None:
        self.config = config
        self._response = response
        self._error = error
        self._delay_s = delay_s

    async def complete(self, request: object) -> object:
        if self._delay_s > 0:
            await asyncio.sleep(self._delay_s)
        if self._error is not None:
            raise self._error

        class _Resp:
            content = self._response

        return _Resp()


@pytest.mark.offline
class TestValidationResult:
    """ValidationResult dataclass tests."""

    def test_to_dict(self) -> None:
        r = ValidationResult(
            provider="openai",
            provider_type=ProviderType.OPENAI,
            status=ValidationStatus.OK,
            latency_ms=42.5,
            model_used="gpt-4o-mini",
            response_preview="pong",
        )
        d = r.to_dict()
        assert d["provider"] == "openai"
        assert d["status"] == "ok"
        assert d["latency_ms"] == 42.5
        assert d["model_used"] == "gpt-4o-mini"
        assert d["response_preview"] == "pong"
        assert "validated_at" in d


@pytest.mark.offline
class TestProviderValidator:
    """ProviderValidator tests."""

    async def test_validate_disabled_provider(self) -> None:
        validator = ProviderValidator()
        config = _make_config(enabled=False)
        result = await validator.validate_provider(config)
        assert result.status == ValidationStatus.NOT_CONFIGURED
        assert "disabled" in (result.error or "").lower()

    async def test_validate_provider_no_api_key(self) -> None:
        validator = ProviderValidator()
        config = _make_config(api_key=None)
        result = await validator.validate_provider(config)
        assert result.status == ValidationStatus.NOT_CONFIGURED
        assert "api key" in (result.error or "").lower()

    async def test_validate_provider_local_no_key(self) -> None:
        """Ollama and LM Studio don't need an API key."""
        validator = ProviderValidator(
            provider_factory=lambda c: _MockProvider(c, response="ok"),
        )
        config = _make_config(
            ptype=ProviderType.OLLAMA,
            api_key=None,
            models=["llama3.2"],
        )
        result = await validator.validate_provider(config)
        assert result.status == ValidationStatus.OK
        assert result.response_preview == "ok"

    async def test_validate_ok(self) -> None:
        validator = ProviderValidator(
            provider_factory=lambda c: _MockProvider(c, response="pong"),
        )
        config = _make_config()
        result = await validator.validate_provider(config)
        assert result.status == ValidationStatus.OK
        assert result.latency_ms is not None
        assert result.latency_ms >= 0
        assert result.response_preview == "pong"
        assert result.model_used == "gpt-4o-mini"

    async def test_validate_uses_config_models(self) -> None:
        validator = ProviderValidator(
            provider_factory=lambda c: _MockProvider(c),
        )
        config = _make_config(models=["gpt-4o"])
        result = await validator.validate_provider(config)
        assert result.model_used == "gpt-4o"

    async def test_validate_timeout(self) -> None:
        validator = ProviderValidator(
            timeout_s=0.1,
            provider_factory=lambda c: _MockProvider(c, delay_s=1.0),
        )
        config = _make_config()
        result = await validator.validate_provider(config)
        assert result.status == ValidationStatus.TIMEOUT

    async def test_validate_unauthorized(self) -> None:
        validator = ProviderValidator(
            provider_factory=lambda c: _MockProvider(
                c, error=Exception("401 Unauthorized: invalid api key"),
            ),
        )
        config = _make_config()
        result = await validator.validate_provider(config)
        assert result.status == ValidationStatus.UNAUTHORIZED

    async def test_validate_rate_limited(self) -> None:
        validator = ProviderValidator(
            provider_factory=lambda c: _MockProvider(
                c, error=Exception("429 Too Many Requests: rate limit exceeded"),
            ),
        )
        config = _make_config()
        result = await validator.validate_provider(config)
        assert result.status == ValidationStatus.RATE_LIMITED

    async def test_validate_unreachable(self) -> None:
        validator = ProviderValidator(
            provider_factory=lambda c: _MockProvider(
                c, error=ConnectionError("connection refused"),
            ),
        )
        config = _make_config()
        result = await validator.validate_provider(config)
        assert result.status == ValidationStatus.UNREACHABLE

    async def test_validate_unknown_error(self) -> None:
        validator = ProviderValidator(
            provider_factory=lambda c: _MockProvider(
                c, error=ValueError("something weird"),
            ),
        )
        config = _make_config()
        result = await validator.validate_provider(config)
        assert result.status == ValidationStatus.UNKNOWN_ERROR

    async def test_validate_all_providers_in_parallel(self) -> None:
        validator = ProviderValidator(
            provider_factory=lambda c: _MockProvider(c, response="ok"),
        )
        configs = [
            _make_config(ProviderType.OPENAI, "OpenAI"),
            _make_config(ProviderType.ANTHROPIC, "Anthropic"),
            _make_config(ProviderType.GOOGLE, "Google"),
        ]
        report = await validator.validate_all(configs=configs)
        assert report.total_providers == 3
        assert report.ok_count == 3
        assert report.failed_count == 0
        assert report.not_configured_count == 0

    async def test_validate_all_mixed_statuses(self) -> None:
        def factory(c: ProviderConfig) -> _MockProvider:
            if c.name == "bad":
                return _MockProvider(c, error=Exception("401 unauthorized"))
            return _MockProvider(c, response="ok")
        validator = ProviderValidator(provider_factory=factory)
        configs = [
            _make_config(ProviderType.OPENAI, "good"),
            _make_config(ProviderType.ANTHROPIC, "bad"),
            _make_config(ProviderType.GOOGLE, "no-key", api_key=None),
        ]
        report = await validator.validate_all(configs=configs)
        assert report.total_providers == 3
        assert report.ok_count == 1
        assert report.failed_count == 1
        assert report.not_configured_count == 1

    async def test_validate_all_empty_configs(self) -> None:
        validator = ProviderValidator()
        report = await validator.validate_all(configs=[])
        assert report.total_providers == 0
        assert report.ok_count == 0

    async def test_validate_all_without_configs_uses_router(self) -> None:
        """If no configs given and no router initialized, returns empty report."""
        validator = ProviderValidator()
        report = await validator.validate_all()
        assert isinstance(report, ValidationReport)
        assert report.total_providers == 0

    def test_classify_error_variants(self) -> None:
        validator = ProviderValidator()
        s, _ = validator._classify_error(Exception("401 unauthorized"))
        assert s == ValidationStatus.UNAUTHORIZED
        s, _ = validator._classify_error(Exception("403 forbidden"))
        assert s == ValidationStatus.UNAUTHORIZED
        s, _ = validator._classify_error(Exception("429 rate limit"))
        assert s == ValidationStatus.RATE_LIMITED
        s, _ = validator._classify_error(ConnectionError("connection refused"))
        assert s == ValidationStatus.UNREACHABLE
        s, _ = validator._classify_error(ValueError("weird"))
        assert s == ValidationStatus.UNKNOWN_ERROR


@pytest.mark.offline
class TestValidationReport:
    """ValidationReport serialization tests."""

    def test_to_dict(self) -> None:
        report = ValidationReport(
            results=[
                ValidationResult(
                    provider="openai",
                    provider_type=ProviderType.OPENAI,
                    status=ValidationStatus.OK,
                ),
                ValidationResult(
                    provider="bad",
                    provider_type=ProviderType.CUSTOM,
                    status=ValidationStatus.UNAUTHORIZED,
                ),
            ],
            started_at="2025-01-01T00:00:00Z",
            finished_at="2025-01-01T00:00:01Z",
            total_providers=2,
            ok_count=1,
            failed_count=1,
            not_configured_count=0,
        )
        d = report.to_dict()
        assert d["total_providers"] == 2
        assert d["ok_count"] == 1
        assert d["failed_count"] == 1
        assert len(d["results"]) == 2
        assert d["results"][0]["status"] == "ok"
        assert d["results"][1]["status"] == "unauthorized"
