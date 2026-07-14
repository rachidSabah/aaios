"""Retry policy — per-step retry configuration."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

__all__ = ["BackoffStrategy", "RetryPolicy"]


class BackoffStrategy(StrEnum):
    """How retry delay grows between attempts."""

    CONSTANT = "constant"  # same delay every time
    LINEAR = "linear"  # delay = initial_delay * attempt
    EXPONENTIAL = "exponential"  # delay = initial_delay * (2 ** (attempt - 1))


class RetryPolicy(BaseModel):
    """Per-step retry policy.

    Defaults match the architecture doc: max 3 attempts, exponential backoff,
    1s initial delay, 60s max delay. ``retryable_errors`` and
    ``non_retryable_errors`` are matched against the error category the
    agent reports (``transient``, ``timeout``, ``rate_limit``,
    ``permission_denied``, ``validation_error``, etc.).
    """

    model_config = ConfigDict(frozen=True)

    max_attempts: int = Field(default=3, ge=1)
    backoff: BackoffStrategy = Field(default=BackoffStrategy.EXPONENTIAL)
    initial_delay_s: float = Field(default=1.0, ge=0.0)
    max_delay_s: float = Field(default=60.0, ge=0.0)
    retryable_errors: list[str] = Field(
        default_factory=lambda: ["transient", "timeout", "rate_limit"],
    )
    non_retryable_errors: list[str] = Field(
        default_factory=lambda: ["permission_denied", "validation_error"],
    )

    def should_retry(self, error_category: str, attempt: int) -> bool:
        """Return True if the step should be retried.

        Args:
            error_category: the category of error (e.g. 'transient', 'validation_error').
            attempt: the current attempt number (1 = first try, 2 = first retry, etc.).
        """
        if attempt >= self.max_attempts:
            return False
        if error_category in self.non_retryable_errors:
            return False
        if error_category in self.retryable_errors:
            return True
        # Unknown error category — default to retry (safer for transient issues)
        return True

    def delay_for_attempt(self, attempt: int) -> float:
        """Return the delay (in seconds) before the next attempt.

        ``attempt`` is the attempt that just failed (1-indexed). The delay
        is for the *next* attempt (attempt + 1).
        """
        if self.backoff == BackoffStrategy.CONSTANT:
            delay = self.initial_delay_s
        elif self.backoff == BackoffStrategy.LINEAR:
            delay = self.initial_delay_s * attempt
        else:  # EXPONENTIAL
            delay = self.initial_delay_s * (2 ** (attempt - 1))
        return min(delay, self.max_delay_s)
