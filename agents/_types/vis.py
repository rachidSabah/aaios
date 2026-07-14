"""VisionAgent — image and video analysis."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from agents._types.gen import GenericAgent


@runtime_checkable
class VisionAgent(GenericAgent, Protocol):
    """The Vision agent type.

    Capabilities advertised: ``vision.caption``, ``vision.detect``,
    ``vision.ocr``, ``vision.compare``.

    Uses vision-capable models via the Model Router.
    """

    async def caption(self, image: bytes) -> str:
        """Generate a caption for an image."""
        ...

    async def detect(self, image: bytes, target: str) -> Any:  # returns DetectionResult
        """Detect objects of a target class in an image."""
        ...

    async def ocr(self, image: bytes) -> str:
        """OCR an image. Returns extracted text."""
        ...

    async def compare(self, image_a: bytes, image_b: bytes) -> Any:  # returns CompareResult
        """Compare two images. Returns similarity + differences."""
        ...
