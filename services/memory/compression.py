"""Memory compression and summarization.

Long-term memory grows unboundedly. The compression scheduler periodically
summarizes clusters of old items into single summary items, reducing the
total item count while preserving the essential information.

Summarization is done via the Model Router (LLM call). The scheduler runs
in the background and targets the oldest, least-accessed items first.

Phase 7: implements the structure and a simple rule-based summarizer (no
LLM call — that requires the Model Router to be wired in Phase 8). The
LLM-based summarizer is a drop-in replacement once the router is available.
"""

from __future__ import annotations

import asyncio
from typing import Any
from uuid import UUID

from core.contracts.memory.item import MemoryItem, MemoryScope
from core.contracts.timestamp import utc_now
from core.logging import get_logger

_log = get_logger(__name__)

__all__ = ["CompressionScheduler", "SummarizationResult", "Summarizer"]


class SummarizationResult:
    """The result of summarizing a set of items."""

    def __init__(
        self,
        summary: MemoryItem,
        source_ids: list[UUID],
        tokens_before: int,
        tokens_after: int,
    ) -> None:
        self.summary = summary
        self.source_ids = source_ids
        self.tokens_before = tokens_before
        self.tokens_after = tokens_after
        self.compression_ratio = tokens_after / max(1, tokens_before)


class Summarizer:
    """Summarizes a set of memory items into a single summary item.

    Phase 7: uses a simple extractive summarizer (first sentence + key terms).
    Phase 8+: will use the Model Router for abstractive summarization.
    """

    async def summarize(
        self,
        items: list[MemoryItem],
        scope: MemoryScope,
        *,
        max_words: int = 200,
    ) -> MemoryItem:
        """Summarize a list of items into a single MemoryItem."""
        if not items:
            raise ValueError("Cannot summarize an empty list of items")

        # Extractive: take the first sentence of each item, up to max_words
        sentences: list[str] = []
        word_count = 0
        for item in items:
            first_sentence = item.content.split(".")[0].strip()
            if first_sentence:
                words = first_sentence.split()
                if word_count + len(words) > max_words:
                    break
                sentences.append(first_sentence)
                word_count += len(words)

        summary_text = f"Summary of {len(items)} items:\n" + ". ".join(sentences) + "."

        return MemoryItem.create(
            scope=scope,
            content=summary_text,
            content_type="text",
            metadata={
                "summarized_count": len(items),
                "summarized_at": utc_now().isoformat(),
                "summarizer": "extractive-v1",
            },
        )


class CompressionScheduler:
    """Schedules and runs memory compression.

    Runs in the background. Every ``interval_s`` seconds, it checks each
    scope for items that are:
      - Older than ``min_age_s``
      - Not already summaries
      - In groups of at least ``min_cluster_size``

    And summarizes them.

    The actual item storage (deleting old items, inserting the summary) is
    done by the Memory Manager — the scheduler just identifies what to
    compress and calls the summarizer.
    """

    def __init__(
        self,
        *,
        summarizer: Summarizer | None = None,
        interval_s: float = 300.0,
        min_age_s: float = 86400.0,  # 1 day
        min_cluster_size: int = 5,
    ) -> None:
        self._summarizer = summarizer or Summarizer()
        self._interval_s = interval_s
        self._min_age_s = min_age_s
        self._min_cluster_size = min_cluster_size
        self._task: asyncio.Task[None] | None = None
        self._running = False
        self._compression_callback: Any = (
            None  # callable[[MemoryItem, list[UUID]], Awaitable[None]]
        )

    def set_compression_callback(
        self,
        callback: Any,  # callable[[MemoryItem, list[UUID]], Awaitable[None]]
    ) -> None:
        """Set the callback called when items are compressed.

        The callback receives (summary_item, source_item_ids) and is
        responsible for storing the summary and deleting the sources.
        Typically the Memory Manager.
        """
        self._compression_callback = callback

    async def start(self) -> None:
        """Start the background compression loop."""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(
            self._loop(),
            name="memory.compression",
        )
        _log.info("compression.started", interval_s=self._interval_s)

    async def stop(self) -> None:
        """Stop the background loop."""
        self._running = False
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        _log.info("compression.stopped")

    async def _loop(self) -> None:
        """Background loop (placeholder — actual compression requires the Memory Manager)."""
        while self._running:
            try:
                await asyncio.sleep(self._interval_s)
                # The actual compression logic is triggered by the Memory Manager,
                # which has access to the vector store and can find old items.
            except asyncio.CancelledError:
                break
            except Exception:
                _log.exception("compression.loop_error")

    async def compress_items(
        self,
        items: list[MemoryItem],
        scope: MemoryScope,
    ) -> SummarizationResult | None:
        """Compress a set of items into a summary.

        Returns the SummarizationResult, or None if there are too few items.
        """
        if len(items) < self._min_cluster_size:
            return None

        tokens_before = sum(len(item.content) // 4 for item in items)
        summary = await self._summarizer.summarize(items, scope)
        summary.summarizes = [item.id for item in items]
        tokens_after = len(summary.content) // 4

        result = SummarizationResult(
            summary=summary,
            source_ids=[item.id for item in items],
            tokens_before=tokens_before,
            tokens_after=tokens_after,
        )

        # Call the callback if set
        if self._compression_callback is not None:
            await self._compression_callback(summary, result.source_ids)

        _log.info(
            "compression.completed",
            scope=str(scope),
            source_count=len(items),
            ratio=result.compression_ratio,
        )
        return result
