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
import json
import os
import shutil
import socket
import sys
from pathlib import Path
from typing import Any

from core.logging import LoggingConfig, get_logger, init_logging

_log = get_logger(__name__)

__all__ = ["boot_and_serve", "main"]


async def _start_9router() -> None:
    """Check if 9router is running. If not, start it in the background."""
    # 1. Route standalone Claude Code CLI through 9router
    try:
        claude_dir = Path.home() / ".claude"
        claude_dir.mkdir(parents=True, exist_ok=True)
        config_path = claude_dir / "config.json"
        
        config_data = {}
        if config_path.is_file():
            try:
                config_data = json.loads(config_path.read_text(encoding="utf-8"))
            except Exception:
                pass
                
        config_data["anthropic_api_base"] = "http://localhost:20128/v1"
        if not config_data.get("anthropic_api_key"):
            config_data["anthropic_api_key"] = "sk_9router"
            
        config_path.write_text(json.dumps(config_data, indent=2), encoding="utf-8")
        _log.info("aaios.start.claude_cli_routed", config_path=str(config_path))
    except Exception as e:
        _log.warning("aaios.start.claude_routing_failed", error=str(e))

    # 2. Check if already running on port 20128
    is_running = False
    try:
        with socket.create_connection(("127.0.0.1", 20128), timeout=0.5):
            is_running = True
    except Exception:
        pass
        
    if is_running:
        _log.info("aaios.start.9router_already_running", port=20128)
        return

    # 3. Find 9router binary path
    binary_path = None
    try:
        config_paths = [
            Path(os.environ.get("ProgramData", "C:\\ProgramData")) / "AAiOS" / "config" / "agents.json",
            Path.home() / ".config" / "aaios" / "agents.json",
            Path("config") / "agents.json"
        ]
        for p in config_paths:
            if p.is_file():
                with open(p, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    cfg = data.get("9router", {})
                    if cfg.get("binary_path"):
                        binary_path = cfg["binary_path"]
                        break
    except Exception:
        pass

    if not binary_path:
        binary_path = shutil.which("9router")

    if not binary_path:
        _log.warning("aaios.start.9router_binary_not_found", msg="9router binary not found. Skipping startup.")
        return

    # 4. Spawn 9router process in the background
    _log.info("aaios.start.starting_9router", binary=binary_path)
    try:
        # Run in tray mode, port 20128, no browser
        if binary_path.lower().endswith((".cmd", ".bat")):
            proc = await asyncio.create_subprocess_shell(
                f'"{binary_path}" -p 20128 -n -t',
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL
            )
        else:
            proc = await asyncio.create_subprocess_exec(
                binary_path, "-p", "20128", "-n", "-t",
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL
            )
        
        await asyncio.sleep(1.0)
        
        is_running_now = False
        try:
            with socket.create_connection(("127.0.0.1", 20128), timeout=0.5):
                is_running_now = True
        except Exception:
            pass
            
        if is_running_now:
            _log.info("aaios.start.9router_started_successfully", port=20128)
        else:
            _log.warning("aaios.start.9router_tray_failed_trying_direct")
            if binary_path.lower().endswith((".cmd", ".bat")):
                proc = await asyncio.create_subprocess_shell(
                    f'"{binary_path}" -p 20128 -n',
                    stdout=asyncio.subprocess.DEVNULL,
                    stderr=asyncio.subprocess.DEVNULL
                )
            else:
                proc = await asyncio.create_subprocess_exec(
                    binary_path, "-p", "20128", "-n",
                    stdout=asyncio.subprocess.DEVNULL,
                    stderr=asyncio.subprocess.DEVNULL
                )
            await asyncio.sleep(1.0)
            _log.info("aaios.start.9router_started_direct", port=20128)
    except Exception as e:
        _log.error("aaios.start.9router_launch_failed", error=str(e))


async def _start_web_ui() -> None:
    """Check if Next.js Web UI is running. If not, start it in the background."""
    import socket
    import shutil
    from pathlib import Path

    # 1. Check if already running on port 3000
    is_running = False
    try:
        with socket.create_connection(("127.0.0.1", 3000), timeout=0.5):
            is_running = True
    except Exception:
        pass

    if is_running:
        _log.info("aaios.start.web_ui_already_running", port=3000)
        return

    # 2. Find pnpm binary
    pnpm_path = shutil.which("pnpm")
    if not pnpm_path:
        _log.warning("aaios.start.pnpm_not_found", msg="pnpm binary not found. Skipping web UI startup.")
        return

    # 3. Start Next.js dev server in the background
    app_root = Path(__file__).parent.parent.resolve()
    _log.info("aaios.start.starting_web_ui", root=str(app_root), binary=pnpm_path)

    try:
        if pnpm_path.lower().endswith((".cmd", ".bat")):
            proc = await asyncio.create_subprocess_shell(
                f'"{pnpm_path}" --filter @aaios/web dev',
                cwd=str(app_root),
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL
            )
        else:
            proc = await asyncio.create_subprocess_exec(
                pnpm_path, "--filter", "@aaios/web", "dev",
                cwd=str(app_root),
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL
            )
        _log.info("aaios.start.web_ui_started_background", pid=proc.pid)
    except Exception as e:
        _log.error("aaios.start.web_ui_launch_failed", error=str(e))


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

    # Start 9router if configured/available
    await _start_9router()

    # Start Web UI (Next.js Dashboard) if available
    await _start_web_ui()

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
    print(f"  Dashboard: http://localhost:3000")
    print(f"  API:       http://{host}:{port}")
    print(f"  Docs:      http://{host}:{port}/docs")
    print(f"  9router:   http://localhost:20128")
    print(f"  Health:    http://{host}:{port}/healthz")
    print(f"  Agents:    {', '.join(agents_registered) or 'none (install agents)'}")
    print(f"  Providers: {len(router.list_providers())}")
    print(f"{'=' * 60}\n")

    # Start uvicorn
    import uvicorn

    from surfaces.api.app import create_app

    app = create_app()
    config = uvicorn.Config(
        app,
        host=host,
        port=port,
        log_config=None,  # we use structlog
    )
    server = uvicorn.Server(config)

    async def _open_browser_when_ready() -> None:
        """Wait for services to be ready, then open the AAiOS dashboard."""
        await asyncio.sleep(2.0)
        import webbrowser
        try:
            # Primary: AAiOS agentic OS dashboard (Next.js on port 3000)
            webbrowser.open("http://localhost:3000")
            _log.info(
                "aaios.start.browser_opened",
                dashboard_url="http://localhost:3000",
                api_url=f"http://{host}:{port}/docs",
                router_url="http://localhost:20128",
            )
        except Exception as e:
            _log.warning("aaios.start.browser_open_failed", error=str(e))

    asyncio.create_task(_open_browser_when_ready())
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
