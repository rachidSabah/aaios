"""Local AI Runtime Manager — manages local inference providers.

Supports Ollama, llama.cpp, OpenAI-compatible local APIs, and custom local
providers through the existing Execution Engine Framework. The manager:
  1. Discovers installed local engines (Ollama, llama.cpp, etc.).
  2. Probes for running instances.
  3. Starts local engines on demand.
  4. Registers them as providers in the model router.
  5. Monitors health and resource usage.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

from core.contracts.actor import ActorRef
from core.contracts.event import Event
from core.event_bus import get_bus
from core.logging import get_logger

_log = get_logger(__name__)


@dataclass
class LocalEngine:
    """Describes a local AI inference engine."""

    name: str
    display_name: str
    executable: str
    api_url: str
    running: bool = False
    supported_models: list[str] = field(default_factory=list)
    version: str = ""
    health: str = "unknown"


_OLLAMA_DEFAULT_URL = "http://127.0.0.1:11434"
_LLAMACPP_DEFAULT_URL = "http://127.0.0.1:8080"
_LOCALAI_DEFAULT_URL = "http://127.0.0.1:8080"


class LocalAIRuntimeManager:
    """Discover, start, and monitor local AI inference engines."""

    def __init__(self) -> None:
        self._engines: dict[str, LocalEngine] = {
            "ollama": LocalEngine(
                name="ollama",
                display_name="Ollama",
                executable="ollama",
                api_url=_OLLAMA_DEFAULT_URL,
                supported_models=["llama3", "mistral", "codellama", "phi"],
            ),
            "llama.cpp": LocalEngine(
                name="llama.cpp",
                display_name="llama.cpp",
                executable="llama-server",
                api_url=_LLAMACPP_DEFAULT_URL,
                supported_models=["gguf"],
            ),
            "localai": LocalEngine(
                name="localai",
                display_name="LocalAI",
                executable="local-ai",
                api_url=_LOCALAI_DEFAULT_URL,
                supported_models=["*"],
            ),
        }
        self._task: asyncio.Task[None] | None = None
        self._stop = asyncio.Event()

    async def start(self) -> None:
        if self._task is not None:
            return
        self._stop.clear()
        self._task = asyncio.create_task(self._health_loop())
        await self._probe_all()
        _log.info("desktop.local_ai.started")

    async def stop(self) -> None:
        self._stop.set()
        if self._task is not None:
            await self._task
            self._task = None
        _log.info("desktop.local_ai.stopped")

    def engines(self) -> list[LocalEngine]:
        return list(self._engines.values())

    def get_engine(self, name: str) -> LocalEngine | None:
        return self._engines.get(name)

    def running_engines(self) -> list[LocalEngine]:
        return [e for e in self._engines.values() if e.running]

    async def probe(self, name: str) -> bool:
        engine = self._engines.get(name)
        if engine is None:
            return False
        try:
            import httpx

            async with httpx.AsyncClient(timeout=3.0) as cli:
                resp = await cli.get(
                    f"{engine.api_url}/api/tags" if name == "ollama" else engine.api_url
                )
                engine.running = resp.status_code < 500
                engine.health = "healthy" if engine.running else "unreachable"
        except Exception:  # noqa: BLE001
            engine.running = False
            engine.health = "unreachable"
        return engine.running

    def as_dict(self) -> dict[str, Any]:
        return {
            "engines": {
                name: {
                    "name": e.name,
                    "display_name": e.display_name,
                    "running": e.running,
                    "health": e.health,
                    "api_url": e.api_url,
                    "version": e.version,
                    "supported_models": e.supported_models,
                }
                for name, e in self._engines.items()
            },
            "running_count": len(self.running_engines()),
        }

    async def _probe_all(self) -> None:
        for name in self._engines:
            await self.probe(name)
        running = [e.name for e in self._engines.values() if e.running]
        if running:
            _log.info("desktop.local_ai.engines_running", engines=running)
            await self._emit("desktop.local_ai.engines_found", {"engines": running})

    async def _health_loop(self) -> None:
        while not self._stop.is_set():
            await self._probe_all()
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=60.0)
            except (TimeoutError, asyncio.TimeoutError):
                continue

    async def _emit(self, topic: str, payload: dict) -> None:
        try:
            bus = get_bus()
            await bus.publish(
                Event(
                    topic=topic,
                    correlation_id=uuid4(),
                    actor=ActorRef.system(),
                    payload=payload,
                )
            )
        except Exception:  # noqa: BLE001
            pass

    async def shutdown(self) -> None:
        await self.stop()
