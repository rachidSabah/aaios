# AAiOS CLI Reference

The `aaios` command is the primary interface for operating AAiOS.

## Commands

### `aaios version`
Print the installed version.

### `aaios doctor`
Run health checks against a running AAiOS instance. Verifies:
- API server reachable
- Event bus initialized
- Agent registry initialized
- Model router initialized
- All registered agents healthy

### `aaios run <goal>`
Submit a goal to the supervisor for execution.

```bash
aaios run "Generate a Python function that sorts a list"
```

### `aaios start`
Boot the entire AAiOS system in live mode:
- Kernel + event bus + state manager
- Security + gateway
- Model router
- Memory
- Agent registry
- Orchestrator + supervisor
- API server on port 8000

### `aaios dev`
Start the API server + web dashboard in development mode.

### `aaios tasks`
List active tasks.

### `aaios agents`
List registered agents.

### `aaios capabilities`
List all capability namespaces.

### `aaios providers`
List configured LLM providers.

### `aaios models`
List available models across all providers.

### `aaios costs`
Show cost analytics.

### `aaios memory recall <query>`
Recall items from memory matching the query.

### `aaios memory remember <content>`
Store an item in long-term memory.

### `aaios audit`
Query the audit log.

## Global Flags

- `--api-base URL` — override the API server URL (default: `http://127.0.0.1:8000`)
- `--json` — output JSON instead of tables
- `--verbose` — enable verbose logging

## Exit Codes

- `0` — success
- `1` — runtime error
- `2` — configuration error
- `3` — connection error (API server unreachable)
