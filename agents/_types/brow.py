"""BrowserAgent — interactive web automation."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from agents._types.gen import GenericAgent


@runtime_checkable
class BrowserAgent(GenericAgent, Protocol):
    """The Browser agent type.

    Capabilities advertised: ``browser.navigate``, ``browser.click``,
    ``browser.input``, ``browser.extract``, ``browser.screenshot``.

    Distinct from ResearchAgent (which is read-only) — BrowserAgent can
    submit forms, log in (with permission), interact with SPAs.
    """

    async def navigate(self, url: str) -> Any:  # returns NavigateResult
        """Navigate to a URL."""
        ...

    async def click(self, selector: str) -> None:
        """Click an element matching the CSS/XPath selector."""
        ...

    async def input(self, selector: str, value: str) -> None:
        """Type into an input element."""
        ...

    async def extract(self, selector: str) -> Any:  # returns ExtractResult
        """Extract data from elements matching the selector."""
        ...

    async def screenshot(self) -> bytes:
        """Capture the page. Returns PNG bytes."""
        ...
