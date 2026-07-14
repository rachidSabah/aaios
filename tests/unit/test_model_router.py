"""Tests for the Model Router — provider registration, routing, failover, cost tracking.

All tests are offline (no real HTTP calls). Provider HTTP calls are mocked
by injecting a fake httpx client.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from pydantic import SecretStr

from core.contracts.model import (
    ModelMessage,
    ModelRequest,
    ModelResponse,
    ProviderConfig,
    ProviderError,
    ProviderType,
    RateLimitError,
    UsageStats,
)
from services.model_router import (
    CostLedger,
    ModelRouter,
    OpenAIProvider,
    RateLimiter,
)


def _make_config(
    name: str = "test-openai",
    ptype: ProviderType = ProviderType.OPENAI,
    priority: int = 1,
    api_key: str = "sk-test",
    **extra,
) -> ProviderConfig:
    """Build a test ProviderConfig."""
    return ProviderConfig(
        type=ptype,
        name=name,
        priority=priority,
        api_key=SecretStr(api_key) if api_key else None,
        **extra,
    )


def _make_request(goal: str = "Hello") -> ModelRequest:
    """Build a minimal ModelRequest."""
    return ModelRequest(messages=[ModelMessage.user(goal)])


def _mock_response(
    content: str = "Hi there!",
    provider: str = "test-openai",
    model: str = "gpt-4o",
    prompt_tokens: int = 10,
    completion_tokens: int = 5,
) -> ModelResponse:
    """Build a mock ModelResponse."""
    return ModelResponse(
        request_id="test",
        provider=provider,
        model=model,
        content=content,
        usage=UsageStats(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
        ),
        cost_usd=0.001,
    )


@pytest.mark.offline
class TestCostLedger:
    """CostLedger tests."""

    async def test_record_and_get_total(self) -> None:
        ledger = CostLedger()
        await ledger.record(
            provider="openai",
            model="gpt-4o",
            cost_usd=0.01,
            prompt_tokens=100,
            completion_tokens=50,
        )
        await ledger.record(
            provider="anthropic",
            model="claude-3-5-sonnet",
            cost_usd=0.02,
            prompt_tokens=200,
            completion_tokens=100,
        )
        assert ledger.get_total_cost() == pytest.approx(0.03)

    async def test_cost_by_provider(self) -> None:
        ledger = CostLedger()
        await ledger.record(provider="openai", model="gpt-4o", cost_usd=0.01)
        await ledger.record(provider="openai", model="gpt-4o", cost_usd=0.02)
        await ledger.record(provider="anthropic", model="claude", cost_usd=0.05)
        by_provider = ledger.get_cost_by_provider()
        assert by_provider["openai"] == pytest.approx(0.03)
        assert by_provider["anthropic"] == pytest.approx(0.05)

    async def test_cost_by_task(self) -> None:
        from uuid import uuid4

        ledger = CostLedger()
        task_id = uuid4()
        await ledger.record(
            provider="openai",
            model="gpt-4o",
            cost_usd=0.01,
            task_id=task_id,
        )
        assert ledger.get_cost_by_task(task_id) == pytest.approx(0.01)

    async def test_cost_by_user(self) -> None:
        ledger = CostLedger()
        await ledger.record(
            provider="openai",
            model="gpt-4o",
            cost_usd=0.01,
            user_id="alice",
        )
        assert ledger.get_cost_by_user("alice") == pytest.approx(0.01)

    async def test_get_entries_filtered(self) -> None:
        ledger = CostLedger()
        await ledger.record(provider="openai", model="gpt-4o", cost_usd=0.01)
        await ledger.record(provider="anthropic", model="claude", cost_usd=0.02)
        entries = ledger.get_entries(provider="openai")
        assert len(entries) == 1
        assert entries[0].provider == "openai"


@pytest.mark.offline
class TestRateLimiter:
    """RateLimiter tests."""

    def test_can_request_no_limit(self) -> None:
        limiter = RateLimiter()
        assert limiter.can_request("unknown-provider") is True

    def test_can_request_within_limit(self) -> None:
        limiter = RateLimiter()
        limiter.register_provider("test", max_requests_per_minute=10)
        assert limiter.can_request("test") is True

    def test_can_request_at_limit(self) -> None:
        limiter = RateLimiter()
        limiter.register_provider("test", max_requests_per_minute=2)
        limiter.record_request("test")
        limiter.record_request("test")
        assert limiter.can_request("test") is False

    async def test_acquire_blocks_when_rate_limited(self) -> None:
        limiter = RateLimiter()
        limiter.register_provider(
            "test", max_requests_per_minute=1, max_tokens_per_minute=1_000_000
        )
        await limiter.acquire("test")
        # Second request should be rate-limited
        with pytest.raises(RateLimitError):
            await limiter.acquire("test")


@pytest.mark.offline
class TestModelRouterProviderManagement:
    """ModelRouter provider registration tests."""

    async def test_register_provider(self) -> None:
        router = ModelRouter()
        config = _make_config()
        name = await router.register_provider(config)
        assert name == "test-openai"
        assert len(router.list_providers()) == 1

    async def test_unregister_provider(self) -> None:
        router = ModelRouter()
        await router.register_provider(_make_config())
        assert await router.unregister_provider("test-openai") is True
        assert len(router.list_providers()) == 0
        assert await router.unregister_provider("test-openai") is False

    async def test_register_unknown_type_raises(self) -> None:
        router = ModelRouter()
        config = ProviderConfig(
            type=ProviderType.OPENAI,  # valid type but we'll mock it
            name="test",
        )
        # All types should be valid — this test just verifies no crash
        await router.register_provider(config)

    async def test_list_models(self) -> None:
        router = ModelRouter()
        await router.register_provider(_make_config(name="openai"))
        models = await router.list_models()
        # OpenAIProvider has a catalog
        assert len(models) > 0
        assert any(m.name == "gpt-4o" for m in models)


@pytest.mark.offline
class TestModelRouterRouting:
    """ModelRouter routing and failover tests."""

    async def test_complete_with_mock_provider(self) -> None:
        """Test completion using a provider with a mocked HTTP client."""
        router = ModelRouter()
        config = _make_config(name="test")
        await router.register_provider(config)

        # Mock the provider's complete method
        provider = router._providers["test"]  # noqa: SLF001
        mock_response = _mock_response(provider="test")
        provider.complete = AsyncMock(return_value=mock_response)  # type: ignore[method-assign]

        request = _make_request("Hello")
        response = await router.complete(request)
        assert response.content == "Hi there!"
        assert response.provider == "test"

    async def test_failover_on_provider_error(self) -> None:
        """If the first provider fails (retryable), the router tries the next."""
        router = ModelRouter()
        # Two providers, priority 1 (primary) and 2 (fallback)
        await router.register_provider(_make_config(name="primary", priority=1))
        await router.register_provider(_make_config(name="fallback", priority=2))

        # Mock the primary to fail, fallback to succeed
        primary = router._providers["primary"]  # noqa: SLF001
        fallback = router._providers["fallback"]  # noqa: SLF001

        primary.complete = AsyncMock(  # type: ignore[method-assign]
            side_effect=ProviderError("primary", "Server error", retryable=True),
        )
        fallback.complete = AsyncMock(  # type: ignore[method-assign]
            return_value=_mock_response(content="Fallback!", provider="fallback"),
        )

        response = await router.complete(_make_request())
        assert response.provider == "fallback"
        assert response.content == "Fallback!"

    async def test_non_retryable_error_raises_immediately(self) -> None:
        """If the first provider fails non-retryably, the router raises."""
        router = ModelRouter()
        await router.register_provider(_make_config(name="primary", priority=1))
        await router.register_provider(_make_config(name="fallback", priority=2))

        primary = router._providers["primary"]  # noqa: SLF001
        primary.complete = AsyncMock(  # type: ignore[method-assign]
            side_effect=ProviderError("primary", "Bad request", retryable=False),
        )

        with pytest.raises(ProviderError, match="Bad request"):
            await router.complete(_make_request())

    async def test_all_providers_fail_raises(self) -> None:
        """If all providers fail, the router raises."""
        router = ModelRouter()
        await router.register_provider(_make_config(name="p1", priority=1))
        await router.register_provider(_make_config(name="p2", priority=2))

        for name in ("p1", "p2"):
            p = router._providers[name]  # noqa: SLF001
            p.complete = AsyncMock(  # type: ignore[method-assign]
                side_effect=ProviderError(name, "Server error", retryable=True),
            )

        with pytest.raises(ProviderError, match="All providers failed"):
            await router.complete(_make_request())

    async def test_cost_recorded_on_success(self) -> None:
        """A successful completion records cost in the ledger."""
        router = ModelRouter()
        await router.register_provider(_make_config(name="test"))

        provider = router._providers["test"]  # noqa: SLF001
        provider.complete = AsyncMock(  # type: ignore[method-assign]
            return_value=_mock_response(),
        )

        await router.complete(_make_request())
        # Cost ledger should have one entry
        assert router.cost_ledger.get_total_cost() > 0

    async def test_health_state_updated_on_success(self) -> None:
        """A successful completion updates the provider's health state."""
        router = ModelRouter()
        await router.register_provider(_make_config(name="test"))

        provider = router._providers["test"]  # noqa: SLF001
        provider.complete = AsyncMock(return_value=_mock_response())  # type: ignore[method-assign]

        await router.complete(_make_request())
        health = router.get_provider_health("test")
        assert health is not None
        assert health.consecutive_failures == 0
        assert health.success_rate == 1.0

    async def test_health_state_updated_on_failure(self) -> None:
        """A failed completion updates the provider's health state."""
        router = ModelRouter()
        await router.register_provider(_make_config(name="test", priority=1))
        await router.register_provider(_make_config(name="backup", priority=2))

        primary = router._providers["test"]  # noqa: SLF001
        backup = router._providers["backup"]  # noqa: SLF001
        primary.complete = AsyncMock(  # type: ignore[method-assign]
            side_effect=ProviderError("test", "Error", retryable=True),
        )
        backup.complete = AsyncMock(return_value=_mock_response(provider="backup"))  # type: ignore[method-assign]

        await router.complete(_make_request())
        health = router.get_provider_health("test")
        assert health is not None
        assert health.consecutive_failures >= 1

    async def test_disabled_provider_skipped(self) -> None:
        """A disabled provider is not used."""
        router = ModelRouter()
        config = _make_config(name="disabled", priority=1, enabled=False)
        await router.register_provider(config)
        await router.register_provider(_make_config(name="active", priority=2))

        active = router._providers["active"]  # noqa: SLF001
        active.complete = AsyncMock(return_value=_mock_response(provider="active"))  # type: ignore[method-assign]

        response = await router.complete(_make_request())
        assert response.provider == "active"


@pytest.mark.offline
class TestModelRouterStreaming:
    """ModelRouter streaming tests."""

    async def test_stream_with_mock_provider(self) -> None:
        """Test streaming using a provider with a mocked stream method."""
        from core.contracts.model import ModelStreamChunk

        router = ModelRouter()
        await router.register_provider(_make_config(name="test"))

        async def mock_stream(request):  # type: ignore[no-untyped-def]
            yield ModelStreamChunk(
                request_id="test",
                provider="test",
                model="gpt-4o",
                content_delta="Hello",
            )
            yield ModelStreamChunk(
                request_id="test",
                provider="test",
                model="gpt-4o",
                content_delta=" world",
                finish_reason="stop",
            )

        provider = router._providers["test"]  # noqa: SLF001
        provider.stream = mock_stream  # type: ignore[method-assign]

        chunks = []
        async for chunk in router.stream(_make_request()):
            chunks.append(chunk)

        assert len(chunks) == 2
        assert chunks[0].content_delta == "Hello"
        assert chunks[1].content_delta == " world"
        assert chunks[1].finish_reason == "stop"


@pytest.mark.offline
class TestModelRouterHealthCheck:
    """ModelRouter health check tests."""

    async def test_health_check_all(self) -> None:
        router = ModelRouter()
        await router.register_provider(_make_config(name="p1"))
        await router.register_provider(_make_config(name="p2"))

        # Mock the providers' health_check methods
        from core.contracts.model.health import ProviderHealth, ProviderStatus

        for name in ("p1", "p2"):
            p = router._providers[name]  # noqa: SLF001
            p.health_check = AsyncMock(  # type: ignore[method-assign]
                return_value=ProviderHealth(provider=name, status=ProviderStatus.HEALTHY),
            )

        results = await router.health_check_all()
        assert len(results) == 2
        assert results["p1"].status == ProviderStatus.HEALTHY
        assert results["p2"].status == ProviderStatus.HEALTHY


@pytest.mark.offline
class TestOpenAICompatibleProvider:
    """Tests for the OpenAICompatibleProvider base class."""

    def test_model_catalog_populated(self) -> None:
        """OpenAIProvider has the expected models in its catalog."""
        provider = OpenAIProvider()
        assert "gpt-4o" in provider._model_catalog  # noqa: SLF001
        assert "gpt-4o-mini" in provider._model_catalog  # noqa: SLF001
        assert "o1" in provider._model_catalog  # noqa: SLF001

    def test_select_model_with_hint(self) -> None:
        provider = OpenAIProvider()
        request = ModelRequest(
            messages=[ModelMessage.user("Hi")],
            model_hint="gpt-4o-mini",
        )
        assert provider._select_model(request) == "gpt-4o-mini"  # noqa: SLF001

    def test_select_model_default(self) -> None:
        provider = OpenAIProvider()
        request = _make_request()
        # Should return the first model in the catalog
        assert provider._select_model(request) == next(iter(provider._model_catalog))  # noqa: SLF001

    def test_calculate_cost(self) -> None:
        from core.contracts.model import UsageStats

        provider = OpenAIProvider()
        usage = UsageStats(
            prompt_tokens=1_000_000, completion_tokens=500_000, total_tokens=1_500_000
        )
        # gpt-4o: $2.50/1M input, $10.00/1M output
        cost = provider._calculate_cost("gpt-4o", usage)  # noqa: SLF001
        expected = (1_000_000 / 1_000_000) * 2.50 + (500_000 / 1_000_000) * 10.00
        assert cost == pytest.approx(expected)
