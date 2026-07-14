"""Context window manager — per-task bounded context.

Each task gets a context window with a token budget. Items are added to the
window until the budget is reached; then the oldest/lowest-relevance items
are evicted (LRU + relevance score).

The context window is what gets passed to the LLM as the prompt context.
Bounded context prevents the prompt from exceeding the model's context
length, and forces the system to prioritize the most relevant information.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID

from core.contracts.memory.query import RankedItem
from core.logging import get_logger

_log = get_logger(__name__)

__all__ = ["ContextWindow", "ContextWindowManager"]


@dataclass
class ContextWindow:
    """A bounded context window for a task."""

    task_id: UUID
    max_tokens: int = 8000
    _items: list[RankedItem] = field(default_factory=list)
    _current_tokens: int = 0
    _evicted: int = 0

    @property
    def current_tokens(self) -> int:
        """Return the current token count."""
        return self._current_tokens

    @property
    def item_count(self) -> int:
        """Return the number of items in the window."""
        return len(self._items)

    @property
    def evicted_count(self) -> int:
        """Return the number of items evicted."""
        return self._evicted

    def add(self, item: RankedItem) -> bool:
        """Add an item to the context window.

        Returns True if the item was added, False if it was evicted
        (either because it didn't fit, or because the window is full).
        """
        item_tokens = _estimate_tokens(item.item.content)
        if item_tokens > self.max_tokens:
            _log.warning(
                "context_window.item_too_large",
                task_id=str(self.task_id),
                item_tokens=item_tokens,
                max_tokens=self.max_tokens,
            )
            return False

        # Evict items if needed
        while self._current_tokens + item_tokens > self.max_tokens and self._items:
            evicted = self._items.pop()  # remove lowest-relevance (last after sort)
            self._current_tokens -= _estimate_tokens(evicted.item.content)
            self._evicted += 1

        self._items.append(item)
        self._current_tokens += item_tokens
        # Keep sorted by score descending
        self._items.sort(key=lambda i: i.score, reverse=True)
        return True

    def add_many(self, items: list[RankedItem]) -> int:
        """Add multiple items. Returns the count actually added."""
        added = 0
        for item in items:
            if self.add(item):
                added += 1
        return added

    def get_items(self) -> list[RankedItem]:
        """Return the items in the window (highest score first)."""
        return list(self._items)

    def get_content(self) -> str:
        """Return the concatenated content of all items (for the LLM prompt)."""
        return "\n\n".join(r.item.content for r in self._items)

    def clear(self) -> None:
        """Clear the window."""
        self._items.clear()
        self._current_tokens = 0


class ContextWindowManager:
    """Manages per-task context windows.

    Usage:
        manager = ContextWindowManager()
        window = manager.open(task_id, max_tokens=8000)
        window.add(ranked_item)
        content = window.get_content()
        manager.close(task_id)
    """

    def __init__(self, default_max_tokens: int = 8000) -> None:
        self._windows: dict[UUID, ContextWindow] = {}
        self._default_max_tokens = default_max_tokens

    def open(self, task_id: UUID, *, max_tokens: int | None = None) -> ContextWindow:
        """Open a context window for a task."""
        if task_id in self._windows:
            return self._windows[task_id]
        window = ContextWindow(
            task_id=task_id,
            max_tokens=max_tokens or self._default_max_tokens,
        )
        self._windows[task_id] = window
        return window

    def get(self, task_id: UUID) -> ContextWindow | None:
        """Return the context window for a task, or None."""
        return self._windows.get(task_id)

    def close(self, task_id: UUID) -> None:
        """Close and discard a context window."""
        self._windows.pop(task_id, None)

    def list_open(self) -> list[UUID]:
        """Return all open task IDs."""
        return list(self._windows.keys())


def _estimate_tokens(text: str) -> int:
    """Rough token estimate: ~4 characters per token for English text."""
    return max(1, len(text) // 4)
