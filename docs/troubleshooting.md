# AAiOS Troubleshooting

Common issues and their solutions.

## Installation

### `python --version` shows < 3.12
AAiOS requires Python 3.12+. Install via:
- **Windows**: `winget install Python.Python.3.12`
- **Linux**: `sudo apt install python3.12`
- **macOS**: `brew install python@3.12`

### `pnpm: command not found`
Install Node.js 22+ which includes corepack:
```bash
corepack enable
corepack prepare pnpm@latest --activate
```

### `aaios: command not found` after install
Ensure `~/.local/bin` (Linux) or `%APPDATA%\Python\Scripts` (Windows) is on PATH.

## Runtime

### `aaios doctor` reports `event_bus: not_initialized`
Run `aaios start` first — the doctor command checks a running instance.

### Provider validation shows `not_configured`
Set the API key env var (e.g. `OPENAI_API_KEY=sk-...`) or use:
```bash
aaios config set-secret openai_api_key sk-...
```

### Dashboard shows "Could not reach API server"
1. Verify the API server is running: `curl http://127.0.0.1:8000/healthz`
2. Check `NEXT_PUBLIC_API_BASE` env var in the web dashboard
3. Verify CORS isn't blocked (check browser console)

### Memory usage grows unbounded
The event store retains all events. Configure retention:
```yaml
event_store:
  retention_days: 30
  max_events: 1000000
```

### Agent fails to initialize with "No default AgentContext set"
Set the default context on the registry before registering agents:
```python
from services.agent_registry import get_agent_registry
from core.contracts.agent import AgentContext, AgentEnvironment
registry = get_agent_registry()
registry.set_default_context(AgentContext(environment=AgentEnvironment(...)))
```

## Windows-specific

### `sc.exe create` fails with "access denied"
Run PowerShell as Administrator.

### WDAC policy not enforced after publish
WDAC policies activate on next boot. Restart the system.

### AppContainer launch fails with "invalid SID"
Ensure the profile name doesn't contain spaces or special characters.

## Distributed

### Nodes go UNHEALTHY after 30s
Increase `heartbeat_timeout_s` if your network has high latency:
```python
NodeRegistry(heartbeat_timeout_s=60.0, offline_timeout_s=180.0)
```

### Tasks not dispatching to remote nodes
1. Verify the remote node is registered: `await registry.list_all()`
2. Verify the remote node's API server is reachable: `curl http://<address>/healthz`
3. Check the remote node's capabilities include the requested capability

## Performance

### Event bus throughput lower than expected
The default InMemoryEventStore persists every event before dispatch (INV-04).
For high-throughput scenarios, consider the Redis event store adapter.

### Memory recall is slow
Vector search uses hash-based embeddings by default (no semantic matching).
Install the optional `sentence-transformers` extra for real embeddings:
```bash
pip install "aaios[embeddings]"
```

## Getting Help

- GitHub Issues: https://github.com/rachidSabah/aaios/issues
- Discussions: https://github.com/rachidSabah/aaios/discussions
