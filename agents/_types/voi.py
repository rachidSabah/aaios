"""VoiceAgent — speech-to-text and text-to-speech."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from agents._types.gen import GenericAgent


@runtime_checkable
class VoiceAgent(GenericAgent, Protocol):
    """The Voice agent type.

    Capabilities advertised: ``voice.stt``, ``voice.tts``.

    Optional in v1; the interface exists so voice support can be added
    without architectural changes.
    """

    async def stt(self, audio: bytes, *, language: str = "en") -> str:
        """Transcribe audio to text."""
        ...

    async def tts(self, text: str, *, voice: str = "default") -> bytes:
        """Synthesize text to speech. Returns audio bytes."""
        ...
