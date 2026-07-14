"""Tests for the priority queue — 5 levels, aging, concurrency limits."""

from __future__ import annotations

from uuid import uuid4

import pytest

from orchestrator.queue import DEFAULT_CONCURRENCY, Priority, QueueItem


@pytest.mark.offline
class TestPriority:
    """Priority enum tests."""

    def test_priority_levels(self) -> None:
        """5 levels, with CRITICAL highest and BACKGROUND lowest."""
        assert Priority.CRITICAL.level < Priority.HIGH.level
        assert Priority.HIGH.level < Priority.NORMAL.level
        assert Priority.NORMAL.level < Priority.LOW.level
        assert Priority.LOW.level < Priority.BACKGROUND.level

    def test_from_string(self) -> None:
        assert Priority.from_string("critical") == Priority.CRITICAL
        assert Priority.from_string("NORMAL") == Priority.NORMAL
        assert Priority.from_string("background") == Priority.BACKGROUND

    def test_from_string_invalid(self) -> None:
        with pytest.raises(ValueError, match="Invalid priority"):
            Priority.from_string("urgent")

    def test_default_concurrency(self) -> None:
        """Default concurrency limits match the architecture doc."""
        assert DEFAULT_CONCURRENCY[Priority.CRITICAL] == 4
        assert DEFAULT_CONCURRENCY[Priority.HIGH] == 4
        assert DEFAULT_CONCURRENCY[Priority.NORMAL] == 8
        assert DEFAULT_CONCURRENCY[Priority.LOW] == 4
        assert DEFAULT_CONCURRENCY[Priority.BACKGROUND] == 2


@pytest.mark.offline
class TestQueueItem:
    """QueueItem tests."""

    def test_age_s(self) -> None:
        from datetime import timedelta

        from core.contracts.timestamp import utc_now

        item = QueueItem(
            plan_id=uuid4(),
            task_id=uuid4(),
            priority=Priority.NORMAL,
            enqueued_at=utc_now() - timedelta(seconds=10),
        )
        assert 9.0 <= item.age_s() <= 11.0

    def test_effective_priority_no_aging(self) -> None:
        item = QueueItem(
            plan_id=uuid4(),
            task_id=uuid4(),
            priority=Priority.LOW,
        )
        # Fresh item — no promotion
        assert item.get_effective_priority(aging_threshold_s=60.0) == Priority.LOW

    def test_effective_priority_with_aging(self) -> None:
        from datetime import timedelta

        from core.contracts.timestamp import utc_now

        # A LOW item that has waited 120s with a 60s threshold → promoted 2 levels
        item = QueueItem(
            plan_id=uuid4(),
            task_id=uuid4(),
            priority=Priority.LOW,
            enqueued_at=utc_now() - timedelta(seconds=120),
        )
        effective = item.get_effective_priority(aging_threshold_s=60.0)
        # LOW (level 3) - 2 promotions = NORMAL (level 1)... wait, let me check
        # LOW.level = 3, 120/60 = 2 promotions → 3 - 2 = 1 = HIGH
        assert effective == Priority.HIGH

    def test_effective_priority_capped_at_critical(self) -> None:
        from datetime import timedelta

        from core.contracts.timestamp import utc_now

        # A BACKGROUND item that has waited 600s → 10 promotions → capped at CRITICAL
        item = QueueItem(
            plan_id=uuid4(),
            task_id=uuid4(),
            priority=Priority.BACKGROUND,
            enqueued_at=utc_now() - timedelta(seconds=600),
        )
        effective = item.get_effective_priority(aging_threshold_s=60.0)
        assert effective == Priority.CRITICAL
