"""Rate limiter — per-provider token bucket.

Enforces two limits per provider:
  - max_requests_per_minute
  - max_tokens_per_minute

Uses a simple sliding-window counter. If the limit is exceeded, the caller
gets a ``RateLimitError`` and the router falls over to the next provider.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field

from core.contracts.provider import RateLimitError
from core.logging import get_logger

_log = get_logger(__name__)

__all__ = ["RateLimiter", "RateLimitState"]


@dataclass
class RateLimitState:
    """Per-provider rate limit state."""

    provider: str
    max_requests_per_minute: int = 60
    max_tokens_per_minute: int = 100_000
    # Sliding window: list of (timestamp, tokens) for recent requests
    _recent_requests: list[tuple[float, int]] = field(default_factory=list)

    def _prune_old(self, now: float) -> None:
        """Remove entries older than 60 seconds."""
        cutoff = now - 60.0
        self._recent_requests = [(t, n) for t, n in self._recent_requests if t > cutoff]

    def can_request(self, estimated_tokens: int = 0) -> bool:
        """Return True if a request can be made now."""
        now = time.monotonic()
        self._prune_old(now)
        recent_count = len(self._recent_requests)
        recent_tokens = sum(n for _, n in self._recent_requests)
        if recent_count >= self.max_requests_per_minute:
            return False
        if recent_tokens + estimated_tokens > self.max_tokens_per_minute:
            return False
        return True

    def record_request(self, tokens: int = 0) -> None:
        """Record a request."""
        now = time.monotonic()
        self._recent_requests.append((now, tokens))

    def wait_time_s(self, estimated_tokens: int = 0) -> float:
        """Return how long to wait before the next request can be made."""
        now = time.monotonic()
        self._prune_old(now)
        if len(self._recent_requests) < self.max_requests_per_minute:
            recent_tokens = sum(n for _, n in self._recent_requests)
            if recent_tokens + estimated_tokens <= self.max_tokens_per_minute:
                return 0.0
        # Wait until the oldest request falls out of the window
        if self._recent_requests:
            oldest = self._recent_requests[0][0]
            return max(0.0, 60.0 - (now - oldest))
        return 0.0


class RateLimiter:
    """Per-provider rate limiter."""

    def __init__(self) -> None:
        self._states: dict[str, RateLimitState] = {}

    def register_provider(
        self,
        provider: str,
        *,
        max_requests_per_minute: int = 60,
        max_tokens_per_minute: int = 100_000,
    ) -> None:
        """Register a provider's rate limits."""
        self._states[provider] = RateLimitState(
            provider=provider,
            max_requests_per_minute=max_requests_per_minute,
            max_tokens_per_minute=max_tokens_per_minute,
        )

    def can_request(self, provider: str, estimated_tokens: int = 0) -> bool:
        """Return True if a request can be made to ``provider`` now."""
        state = self._states.get(provider)
        if state is None:
            return True  # no limit configured
        return state.can_request(estimated_tokens)

    def record_request(self, provider: str, tokens: int = 0) -> None:
        """Record a request to ``provider``."""
        state = self._states.get(provider)
        if state is not None:
            state.record_request(tokens)

    async def acquire(self, provider: str, estimated_tokens: int = 0) -> None:
        """Block until a request can be made, or raise RateLimitError.

        If the wait would be too long (>30s), raises RateLimitError so the
        router can failover to the next provider.
        """
        state = self._states.get(provider)
        if state is None:
            return  # no limit configured
        wait = state.wait_time_s(estimated_tokens)
        if wait > 30.0:
            raise RateLimitError(provider, retry_after_s=wait)
        if wait > 0:
            _log.info("rate_limiter.waiting", provider=provider, wait_s=round(wait, 2))
            await asyncio.sleep(wait)
        state.record_request(estimated_tokens)
