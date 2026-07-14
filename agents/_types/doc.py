"""DocumentAgent — PDF/DOCX/XLSX/PPTX operations."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from agents._types.gen import GenericAgent


@runtime_checkable
class DocumentAgent(GenericAgent, Protocol):
    """The Document agent type.

    Capabilities advertised: ``doc.create``, ``doc.edit``, ``doc.convert``,
    ``doc.extract``.

    Distinct from CodingAgent (which works on code) and DesktopAgent (which
    works on the screen).
    """

    async def create(self, format: str, content: Any, template: str | None = None) -> bytes:
        """Create a document. Returns the file bytes."""
        ...

    async def edit(self, path: Path, changes: Any) -> bytes:
        """Edit an existing document. Returns the updated bytes."""
        ...

    async def convert(self, path: Path, target_format: str) -> bytes:
        """Convert a document to a different format."""
        ...

    async def extract(self, path: Path) -> Any:  # returns ExtractResult
        """Extract content (text, tables, images) from a document."""
        ...
