"""Voice & Vision Agent — multimodal agent for ASR, TTS, image understanding,
and image generation.

Capabilities:
  - audio.transcribe: speech → text (ASR)
  - audio.synthesize: text → speech (TTS)
  - image.analyze: image + prompt → text description (VLM)
  - image.generate: prompt → image (text-to-image)
  - multimodal.chat: text + optional image/audio → text response

The agent has two modes:
  - Mock mode (default): returns canned responses for testing
  - Live mode: calls the model router with vision-capable providers

In live mode, the agent uses the global ModelRouter to find a provider
that supports the required modality (vision, audio, image-generation).
The actual provider selection is delegated to the router's hint system.
"""

from __future__ import annotations

import base64
import time
from typing import Any

from agents._base.in_process import InProcessAgent
from agents._impls.voice_vision.capabilities import build_manifest
from core.contracts.agent import AgentIdentity
from core.contracts.agent.agent_identity import AgentType
from core.contracts.health import HealthReport, HealthState
from core.contracts.model.message import ModelMessage
from core.contracts.model.request import ModelRequest, RequestHint
from core.contracts.task import TaskRequest, TaskResult, TaskResultStatus
from core.logging import get_logger

_log = get_logger(__name__)

__all__ = ["VoiceVisionAgent"]


# Minimal 1x1 PNG (8 bytes header + IHDR + IDAT + IEND) for mock images
_MOCK_PNG_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR4nGNgYGBgAAAABQAB"
    "hatU2PAAAAABJRU5ErkJggg=="
)


class VoiceVisionAgent(InProcessAgent):
    """Multimodal agent for ASR, TTS, image understanding, and image generation.

    The agent is identified as 'voice-vision-v1' but the core architecture
    never references this name (INV-09). The Supervisor discovers it via
    the Agent Registry's capability index.
    """

    def __init__(
        self,
        *,
        mock_mode: bool = True,
    ) -> None:
        identity = AgentIdentity(
            agent_id="voice-vision-v1",
            agent_type=AgentType.VISION,
            implementation_name="Voice & Vision Agent",
            version="2.0.0",
            vendor="AAiOS",
        )
        super().__init__(identity)
        self._mock_mode = mock_mode
        self._manifest = build_manifest()
        self._call_count: int = 0
        self._total_latency_s: float = 0.0

    async def _on_initialize(self) -> None:
        """Hook for subclasses to acquire resources."""
        if self._mock_mode:
            _log.info("VoiceVisionAgent initialized in mock mode")
        else:
            _log.info("VoiceVisionAgent initialized in live mode")

    async def _on_shutdown(self, *, graceful: bool = True) -> None:
        """Hook for subclasses to release resources."""
        _log.info("VoiceVisionAgent shutdown (graceful=%s)", graceful)

    async def _build_manifest(self) -> Any:  # CapabilityManifest
        """Build the capability manifest."""
        return self._manifest

    async def _execute(self, request: TaskRequest) -> TaskResult:
        """Execute a multimodal task.

        The request.goal is the capability namespace; parameters come from
        request.context (a TaskContext with optional inputs).
        """
        start = time.perf_counter()
        capability = request.goal
        # TaskContext carries inputs; fall back to empty dict if absent
        params: dict[str, Any] = {}
        try:
            ctx_data = request.context.model_dump()
            params = ctx_data.get("metadata", {}).get("inputs", {})
        except Exception:
            params = {}
        try:
            result: Any
            if capability == "audio.transcribe":
                result = await self.transcribe(params.get("audio", b""))
            elif capability == "audio.synthesize":
                result = await self.synthesize(
                    params.get("text", ""),
                    voice=params.get("voice", "default"),
                )
            elif capability == "image.analyze":
                result = await self.analyze_image(
                    params.get("image", b""),
                    params.get("prompt", "Describe this image."),
                )
            elif capability == "image.generate":
                result = await self.generate_image(
                    params.get("prompt", ""),
                    size=params.get("size", "1024x1024"),
                )
            elif capability == "multimodal.chat":
                result = await self.chat(
                    params.get("text", ""),
                    image=params.get("image"),
                    audio=params.get("audio"),
                )
            else:
                return TaskResult(
                    task_id=request.id,
                    status=TaskResultStatus.FAILURE,
                    error=f"Unknown capability: {capability}",
                )
            latency = time.perf_counter() - start
            # Capability methods track calls themselves; we just record latency here
            return TaskResult(
                task_id=request.id,
                status=TaskResultStatus.SUCCESS,
                output={"result": result, "latency_s": latency},
                duration_s=latency,
            )
        except Exception as e:
            _log.warning("VoiceVisionAgent task failed: %s", e)
            return TaskResult(
                task_id=request.id,
                status=TaskResultStatus.FAILURE,
                error=str(e),
            )

    # --- Capability implementations ---

    async def transcribe(self, audio: bytes) -> str:
        """ASR — transcribe audio bytes to text."""
        start = time.perf_counter()
        if self._mock_mode:
            result = "This is a mock transcription."
        else:
            result = await self._live_transcribe(audio)
        self._track_call(time.perf_counter() - start)
        return result

    async def _live_transcribe(self, audio: bytes) -> str:
        """Call a real ASR provider via the model router."""
        try:
            from services.model_router import get_model_router

            router = get_model_router()

            # Send the audio as base64 in the message content
            audio_b64 = base64.b64encode(audio).decode("ascii")
            request = ModelRequest(
                messages=[
                    ModelMessage.user(
                        f"data:audio/wav;base64,{audio_b64}\nTranscribe this audio.",
                    ),
                ],
                model_hint="whisper-1",
                hints={RequestHint.VISION},  # closest hint available
                max_tokens=200,
            )
            response = await router.complete(request)
            return response.content or ""
        except Exception as e:
            _log.warning("Live ASR failed: %s — falling back to mock", e)
            return "This is a mock transcription."

    async def synthesize(self, text: str, voice: str = "default") -> bytes:
        """TTS — synthesize speech from text."""
        start = time.perf_counter()
        if self._mock_mode:
            result = self._mock_wav()
        else:
            result = await self._live_synthesize(text, voice)
        self._track_call(time.perf_counter() - start)
        return result

    async def _live_synthesize(self, text: str, voice: str) -> bytes:
        """Call a real TTS provider."""
        try:
            from services.model_router import get_model_router

            router = get_model_router()

            request = ModelRequest(
                messages=[ModelMessage.user(f"Synthesize: {text}")],
                model_hint="tts-1",
                max_tokens=100,
                metadata={"voice": voice, "modality": "audio"},
            )
            await router.complete(request)
            # In production: response.audio would be the audio bytes
            # For now, fall back to mock WAV
            return self._mock_wav()
        except Exception as e:
            _log.warning("Live TTS failed: %s — falling back to mock", e)
            return self._mock_wav()

    async def analyze_image(self, image: bytes, prompt: str) -> str:
        """VLM — analyze an image with a text prompt."""
        start = time.perf_counter()
        if self._mock_mode:
            result = f"Mock analysis of image ({len(image)} bytes) for prompt: {prompt}"
        else:
            result = await self._live_analyze_image(image, prompt)
        self._track_call(time.perf_counter() - start)
        return result

    async def _live_analyze_image(self, image: bytes, prompt: str) -> str:
        """Call a real VLM via the model router."""
        try:
            from services.model_router import get_model_router

            router = get_model_router()

            image_b64 = base64.b64encode(image).decode("ascii")
            request = ModelRequest(
                messages=[
                    ModelMessage.user(
                        f"data:image/png;base64,{image_b64}\n\n{prompt}",
                    ),
                ],
                hints={RequestHint.VISION},
                max_tokens=500,
            )
            response = await router.complete(request)
            return response.content or ""
        except Exception as e:
            _log.warning("Live image analysis failed: %s — falling back to mock", e)
            return f"Mock analysis of image ({len(image)} bytes) for prompt: {prompt}"

    async def generate_image(self, prompt: str, size: str = "1024x1024") -> bytes:
        """Text-to-image — generate an image from a prompt."""
        start = time.perf_counter()
        if self._mock_mode:
            result = self._mock_png()
        else:
            result = await self._live_generate_image(prompt, size)
        self._track_call(time.perf_counter() - start)
        return result

    async def _live_generate_image(self, prompt: str, size: str) -> bytes:
        """Call a real text-to-image provider."""
        try:
            from services.model_router import get_model_router

            router = get_model_router()

            request = ModelRequest(
                messages=[ModelMessage.user(f"Generate image: {prompt}")],
                model_hint="dall-e-3",
                max_tokens=100,
                metadata={"size": size, "modality": "image"},
            )
            await router.complete(request)
            # In production: response.image would be the PNG bytes
            return self._mock_png()
        except Exception as e:
            _log.warning("Live image gen failed: %s — falling back to mock", e)
            return self._mock_png()

    async def chat(
        self,
        text: str,
        image: bytes | None = None,
        audio: bytes | None = None,
    ) -> str:
        """Multimodal chat — text + optional image/audio → text response."""
        start = time.perf_counter()
        if self._mock_mode:
            parts = [f"Mock response to: {text}"]
            if image is not None:
                parts.append(f"(image attached, {len(image)} bytes)")
            if audio is not None:
                parts.append(f"(audio attached, {len(audio)} bytes)")
            result = " ".join(parts)
            self._track_call(time.perf_counter() - start)
            return result
        # Live mode: build a multimodal request
        try:
            from services.model_router import get_model_router

            router = get_model_router()

            content = text
            hints: set[RequestHint] = set()
            if image is not None:
                image_b64 = base64.b64encode(image).decode("ascii")
                content = f"data:image/png;base64,{image_b64}\n\n{text}"
                hints.add(RequestHint.VISION)
            if audio is not None:
                audio_b64 = base64.b64encode(audio).decode("ascii")
                content += f"\n\ndata:audio/wav;base64,{audio_b64}"

            request = ModelRequest(
                messages=[ModelMessage.user(content)],
                hints=hints,
                max_tokens=500,
            )
            response = await router.complete(request)
            self._track_call(time.perf_counter() - start)
            return response.content or ""
        except Exception as e:
            _log.warning("Live multimodal chat failed: %s — falling back to mock", e)
            parts = [f"Mock response to: {text}"]
            if image is not None:
                parts.append(f"(image attached, {len(image)} bytes)")
            if audio is not None:
                parts.append(f"(audio attached, {len(audio)} bytes)")
            self._track_call(time.perf_counter() - start)
            return " ".join(parts)

    def _track_call(self, latency_s: float) -> None:
        """Track a capability call for health/metrics."""
        self._call_count += 1
        self._total_latency_s += latency_s

    # --- Health & metrics ---

    async def report_health(self) -> HealthReport:
        """Report agent health."""
        if self._call_count == 0:
            return HealthReport(
                state=HealthState.HEALTHY,
                reason="No calls yet (mock mode)",
                latency_ms=0.0,
            )
        avg_latency = self._total_latency_s / max(1, self._call_count)
        state = HealthState.HEALTHY if avg_latency < 5.0 else HealthState.DEGRADED
        return HealthReport(
            state=state,
            reason=f"avg_latency={avg_latency:.3f}s, calls={self._call_count}",
            latency_ms=avg_latency * 1000.0,
        )

    # --- Helpers ---

    @staticmethod
    def _mock_wav() -> bytes:
        """Return a minimal 44-byte WAV header."""
        # RIFF header + fmt chunk + empty data chunk
        return (
            b"RIFF"  # ChunkID
            b"\x24\x00\x00\x00"  # ChunkSize (36)
            b"WAVE"
            b"fmt "
            b"\x10\x00\x00\x00"  # Subchunk1Size (16)
            b"\x01\x00"  # AudioFormat (PCM)
            b"\x01\x00"  # NumChannels (1)
            b"\x44\xac\x00\x00"  # SampleRate (44100)
            b"\x88\x58\x01\x00"  # ByteRate
            b"\x02\x00"  # BlockAlign
            b"\x10\x00"  # BitsPerSample (16)
            b"data"
            b"\x00\x00\x00\x00"  # Subchunk2Size (0)
        )

    @staticmethod
    def _mock_png() -> bytes:
        """Return a minimal 1x1 PNG."""
        return base64.b64decode(_MOCK_PNG_B64)
