"""AAiOS live boot — starts all services and serves immediately.

This is the entry point called by `aaios start` and the install scripts.
It boots the kernel, initializes all services (Model Router, Memory, Security,
Agent Registry, Orchestrator, Supervisor), registers the built-in agents
(Claude Code + Hermes — in real mode, no mock), and starts the API server.

Usage:
    aaios start
    aaios start --port 8000 --host 0.0.0.0
    python -m scripts.start
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path
from typing import Any

from core.logging import LoggingConfig, get_logger, init_logging

_log = get_logger(__name__)

__all__ = ["boot_and_serve", "main"]


async def boot_and_serve(
    *,
    host: str = "127.0.0.1",
    port: int = 8000,
    openai_api_key: str | None = None,
    anthropic_api_key: str | None = None,
    anthropic_base_url: str | None = None,
    project_root: str | None = None,
) -> None:
    """Boot AAiOS fully and start serving.

    This is the main entry point. It:
    1. Initializes logging
    2. Boots the kernel (Event Bus, State Manager, Config, etc.)
    3. Initializes the Security Manager and installs it in the Gateway
    4. Initializes the Model Router (with whatever API keys are available)
    5. Initializes the Memory Manager
    6. Initializes the Agent Registry
    7. Registers Claude Code + Hermes agents (REAL mode — no mock)
    8. Initializes the Orchestrator + Supervisor
    9. Starts the FastAPI server
    """
    # 1. Logging
    init_logging(LoggingConfig(level="INFO", json_output=True))
    _log.info("aaios.start.beginning", host=host, port=port)

    # 2. Kernel boot
    from core.bootstrap import KernelConfig, boot_kernel

    await boot_kernel(
        KernelConfig(
            defaults_path=Path("config/defaults.yaml")
            if Path("config/defaults.yaml").exists()
            else None,
        )
    )
    _log.info("aaios.start.kernel_ready")

    # 3. Security
    from services.security import SecurityManager

    sec_mgr = SecurityManager()
    sec_mgr.install_in_gateway()
    _log.info("aaios.start.security_ready")

    # Set up default roles
    from services.security import Role

    sec_mgr.assign_role("system", Role.OWNER)
    sec_mgr.assign_role("api-user", Role.OWNER)

    # 4. Model Router
    from pydantic import SecretStr

    from core.contracts.provider import ProviderConfig, ProviderType
    from services.model_router import ModelRouter

    router = ModelRouter()

    # Register OpenAI if key available
    openai_key = openai_api_key or os.environ.get("OPENAI_API_KEY")
    if openai_key:
        await router.register_provider(
            ProviderConfig(
                type=ProviderType.OPENAI,
                name="openai",
                priority=1,
                api_key=SecretStr(openai_key),
            )
        )
        _log.info("aaios.start.provider_registered", provider="openai")

    # Register Anthropic if key available
    anthropic_key = anthropic_api_key or os.environ.get("ANTHROPIC_API_KEY")
    if anthropic_key:
        await router.register_provider(
            ProviderConfig(
                type=ProviderType.ANTHROPIC,
                name="anthropic",
                priority=2,
                api_key=SecretStr(anthropic_key),
            )
        )
        _log.info("aaios.start.provider_registered", provider="anthropic")

    # Register Ollama (local, no key needed)
    try:
        await router.register_provider(
            ProviderConfig(
                type=ProviderType.OLLAMA,
                name="ollama",
                priority=10,
                base_url="http://localhost:11434/v1",
            )
        )
        _log.info("aaios.start.provider_registered", provider="ollama")
    except Exception:
        _log.info("aaios.start.ollama_skipped", reason="not available")

    # Check if any provider is available
    if not openai_key and not anthropic_key:
        _log.warning(
            "aaios.start.no_llm_keys",
            msg="No OPENAI_API_KEY or ANTHROPIC_API_KEY set. "
            "LLM features will fail. Set a key and restart.",
        )
    else:
        _log.info("aaios.start.model_router_ready", providers=len(router.list_providers()))

    # 5. Memory
    from services.memory import MemoryManager

    MemoryManager()
    _log.info("aaios.start.memory_ready")

    # 6. Agent Registry
    from core.contracts.agent import AgentEnvironment
    from core.platform import get_platform
    from services.agent_registry import AgentRegistry

    platform = get_platform()
    registry = AgentRegistry()
    env = AgentEnvironment(
        home_dir=platform.home_dir,
        config_dir=platform.config_dir,
        data_dir=platform.data_dir,
        log_dir=platform.log_dir,
        temp_dir=platform.temp_dir,
        sandbox_root=Path(project_root) if project_root else None,
    )
    registry.set_default_context(env)

    # 7. Register agents (REAL mode — no mock)
    agents_registered: list[str] = []

    # Claude Code
    try:
        from agents import ClaudeCodeCodingAgent

        cc_agent = ClaudeCodeCodingAgent(
            project_root=project_root or ".",
            mock_mode=False,  # NEVER mock — fail if no binary
        )
        if cc_agent._mock_mode:  # noqa: SLF001
            _log.warning(
                "aaios.start.claude_code_not_found",
                msg="Claude Code CLI not detected. Install it: npm install -g @anthropic-ai/claude-code",
            )
        else:
            await registry.register(cc_agent)
            agents_registered.append("claude-code-v1")
            _log.info(
                "aaios.start.agent_registered", agent="claude-code-v1", binary=cc_agent._cli_binary
            )  # noqa: SLF001
    except Exception as e:
        _log.warning("aaios.start.claude_code_failed", error=str(e))

    # Hermes
    try:
        from agents import HermesDesktopAgent

        hermes_agent = HermesDesktopAgent(
            mock_mode=False,  # NEVER mock
        )
        if hermes_agent._mock_mode:  # noqa: SLF001
            _log.warning(
                "aaios.start.hermes_not_found",
                msg="Hermes daemon not detected. Run: python scripts/bind_agents.py",
            )
        else:
            await registry.register(hermes_agent)
            agents_registered.append("hermes-desktop-v1")
            _log.info("aaios.start.agent_registered", agent="hermes-desktop-v1")
    except Exception as e:
        _log.warning("aaios.start.hermes_failed", error=str(e))

    # 8. Orchestrator + Supervisor
    from core.event_bus import get_bus
    from orchestrator import TaskOrchestrator
    from orchestrator.checkpoint_store import InMemoryCheckpointStore

    bus = get_bus()
    store = InMemoryCheckpointStore()

    async def step_executor(step: Any) -> dict[str, Any]:
        """Execute a step via the capability selector + agent."""
        from supervisor import CapabilitySelector, NoCandidateError

        selector = CapabilitySelector(registry)
        try:
            selection = selector.select(step.capability)
        except NoCandidateError:
            return {"error": f"No agent for capability: {step.capability}"}
        agent = registry.get(selection.agent_id)
        from uuid import uuid4

        from core.contracts.actor import ActorRef
        from core.contracts.task import TaskContext, TaskRequest

        request = TaskRequest(
            id=uuid4(),
            goal=step.goal,
            context=TaskContext(submitted_by=ActorRef.system()),
        )
        result = await agent.execute_task(request)
        return {"output": result.output, "status": result.status.value}

    orch = TaskOrchestrator(bus=bus, checkpoint_store=store, step_executor=step_executor)
    await orch.start()
    _log.info("aaios.start.orchestrator_ready")

    # 9. Start API server
    _log.info("aaios.start.starting_api", host=host, port=port)
    print(f"\n{'=' * 60}")
    print("  AAiOS v1.0.0 is LIVE")
    print(f"  API:     http://{host}:{port}")
    print(f"  Docs:    http://{host}:{port}/docs")
    print(f"  Health:  http://{host}:{port}/healthz")
    print(f"  Agents:  {', '.join(agents_registered) or 'none (install agents)'}")
    print(f"  Providers: {len(router.list_providers())}")
    print(f"{'=' * 60}\n")

    # Start uvicorn
    import uvicorn

    from surfaces.api.app import create_app

    app = create_app()
    config = uvicorn.Config(app, host=host, port=port, log_level="info")
    server = uvicorn.Server(config)
    await server.serve()


def main() -> int:
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Start AAiOS (live mode)")
    parser.add_argument("--host", default="127.0.0.1", help="Bind host (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8000, help="Bind port (default: 8000)")
    parser.add_argument("--openai-key", type=str, default=None, help="OpenAI API key")
    parser.add_argument("--anthropic-key", type=str, default=None, help="Anthropic API key")
    parser.add_argument("--anthropic-base-url", type=str, default=None, help="Anthropic proxy URL")
    parser.add_argument("--project-root", type=str, default=None, help="Project root for agents")
    args = parser.parse_args()

    try:
        asyncio.run(
            boot_and_serve(
                host=args.host,
                port=args.port,
                openai_api_key=args.openai_key,
                anthropic_api_key=args.anthropic_key,
                anthropic_base_url=args.anthropic_base_url,
                project_root=args.project_root,
            )
        )
    except KeyboardInterrupt:
        print("\nAAiOS shutting down...")
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
