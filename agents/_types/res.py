"""ResearchAgent — web research."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from agents._types.gen import GenericAgent


@runtime_checkable
class ResearchAgent(GenericAgent, Protocol):
    """The Research agent type.

    Capabilities advertised: ``web.search``, ``web.fetch``, ``web.summarize``,
    ``cite.format``.

    Permissions: network (HTTP/HTTPS only); filesystem (write to scratch only).
    """

    async def search(self, query: str, *, max_results: int = 10) -> Any:  # returns SearchResult
        """Search the web. Returns ranked results with snippets + URLs."""
        ...

    async def fetch(self, url: str) -> Any:  # returns FetchResult
        """Fetch a URL and extract its main content."""
        ...

    async def summarize(self, content: str, *, max_words: int = 200) -> str:
        """Summarize content into a concise form."""
        ...

    async def cite(self, sources: list[Any], style: str = "apa") -> str:
        """Format citations for a list of sources."""
        ...
