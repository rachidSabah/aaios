# Developer Guide

## Architecture Overview

AAiOS is a 5-layer system:

| Layer | Package | Purpose |
|-------|---------|---------|
| L1 Kernel | `core/` | Event Bus, State Manager, Config, Logging, Telemetry, DI, Tool/Prompt Registry, Gateway |
| L2 Services | `services/` | Model Router, Memory, MCP, Plugins, Security, Agent Registry |
| L3 Agents | `agents/` | GenericAgent implementations (16 types, 3 implementation styles) |
| L4 Supervision | `supervisor/`, `orchestrator/` | Supervisor, Planner, Reflection, QA, Task Orchestrator |
| L5 Surfaces | `surfaces/` | API (FastAPI), CLI (Typer), Web (Next.js), Desktop (Tauri) |

## Key Principles

1. **Genericism** — the Supervisor orchestrates capabilities, not products. No agent name is hardcoded in core (INV-09).
2. **Zero-trust** — all I/O goes through the Gateway (INV-02). All permissions are checked.
3. **Event-sourced** — all state changes are events. Replayable, auditable.
4. **Windows-first** — native Windows Services, Task Scheduler, PowerShell.

## Adding a New LLM Provider

1. Create `services/model_router/providers/my_provider.py`:

```python
from services.model_router.providers.openai_compatible import OpenAICompatibleProvider
from core.contracts.provider import ModelInfo, ProviderType

class MyProvider(OpenAICompatibleProvider):
    _provider_type = ProviderType.CUSTOM
    _default_base_url = 'https://api.myprovider.com/v1'
    _model_catalog = {
        'my-model': ModelInfo(
            name='my-model', display_name='My Model', provider='my_provider',
            supports_tools=True, context_window=32_000,
            cost_per_1m_input_usd=1.0, cost_per_1m_output_usd=2.0,
        ),
    }
```

2. Register it in `services/model_router/router.py` (`_PROVIDER_CLASSES`).
3. Add tests in `tests/unit/`.
4. Submit a PR.

## Adding a New Agent

Use the Agent SDK to scaffold:

```bash
python -c "
from services.agent_sdk import scaffold_agent
from pathlib import Path
scaffold_agent(
    name='my-agent',
    agent_type='research',
    style='in_process',
    output_dir=Path('./plugins/my-agent'),
)
"
```

This generates:
- `plugin.json` — manifest
- `__init__.py`
- `agent/agent.py` — agent class (implements GenericAgent)
- `README.md`

Implement the agent's `_execute()` method, register it with the Agent Registry, and the Supervisor will automatically discover it via capability-based selection.

## Adding a New Tool

```python
from core.registry import Tool, get_tool_registry

async def my_tool(args: dict, ctx) -> dict:
    return {'result': 'done'}

registry = get_tool_registry()
registry.register(Tool(
    name='my.tool',
    description='Does something useful',
    input_schema={'type': 'object', 'properties': {}},
    handler=my_tool,
))
```

## Running Tests

```powershell
# All tests (excluding slow)
tasks test

# Unit tests only
tasks test-unit

# Integration tests
python -m pytest tests/integration/ --no-cov

# Security tests
python -m pytest tests/security/ --no-cov

# Performance benchmarks
python -m pytest tests/performance/ --no-cov -s

# With slow tests
python -m pytest tests/ --no-cov -m "slow"
```

## Code Style

- **Python**: ruff (lint + format), mypy --strict, bandit
- **TypeScript**: ESLint, Prettier, strict tsconfig
- **Commits**: Conventional Commits (`feat(scope): subject`)
- **PRs**: one concern per PR, INV-01 through INV-12 checklist

## Debugging

### Kernel boot
```python
from core.bootstrap import boot_kernel, shutdown_kernel
import asyncio

async def main():
    await boot_kernel()
    # ... inspect state ...
    await shutdown_kernel()

asyncio.run(main())
```

### Event bus replay
```python
from core.event_bus import get_bus

bus = get_bus()
events = await bus.store.replay(stream_id=str(task_id))
for e in events:
    print(f'{e.timestamp} {e.topic} {e.payload}')
```

### Audit log verification
```python
from services.security import get_security_manager

mgr = get_security_manager()
valid = await mgr.verify_audit_chain()
print(f'Audit chain valid: {valid}')
```
