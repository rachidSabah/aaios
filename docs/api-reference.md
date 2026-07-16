# AAiOS API Reference

REST API exposed by the AAiOS API server (default port 8000).

## Health

### `GET /healthz`
Liveness probe. Returns `{status: "ok", version: "...", timestamp: "..."}`.

### `GET /readyz`
Readiness probe. Returns per-subsystem check results.

### `GET /metrics`
Basic metrics (Prometheus format planned for v2.1).

## Tasks

### `POST /api/v1/tasks`
Submit a new task. Body: `{goal: "...", priority: "normal"}`.
Returns `{task_id: "...", status: "queued"}`.

### `GET /api/v1/tasks`
List active tasks.

### `GET /api/v1/tasks/{task_id}`
Get task details including steps.

### `POST /api/v1/tasks/{task_id}/pause|resume|cancel`
Control task lifecycle.

## Agents

### `GET /api/v1/agents`
List registered agents with health + capabilities.

### `GET /api/v1/agents/{agent_id}`
Get agent details.

### `GET /api/v1/capabilities`
List all capability namespaces across registered agents.

## Memory

### `POST /api/v1/memory/remember`
Store a memory item. Body: `{scope_type: "long_term", content: "...", content_type: "text"}`.

### `POST /api/v1/memory/recall`
Recall items matching a query. Body: `{query: "...", k: 10}`.

## Workflows (v2.0)

### `POST /api/v1/workflows`
Create a new workflow. Body: `{name: "...", nodes: [...], edges: [...]}`.

### `GET /api/v1/workflows`
List all saved workflows.

### `GET /api/v1/workflows/{workflow_id}`
Get a workflow by ID.

### `PUT /api/v1/workflows/{workflow_id}`
Update a workflow.

### `DELETE /api/v1/workflows/{workflow_id}`
Delete a workflow.

## Monitoring (v2.0)

### `GET /api/v1/monitor/snapshot`
Get a point-in-time snapshot of system state (event counts, active agents,
recent events, per-minute buckets).

### `GET /api/v1/monitor/timeseries?metric=event_count&window_minutes=60`
Get a time series for a specific metric.

### `POST /api/v1/monitor/record`
Manually record a metric event (for testing or external integrations).

## Analytics (v2.0)

### `GET /api/v1/analytics/summary`
Top-line summary: totals, rates, top agents/capabilities.

### `GET /api/v1/analytics/costs?window_minutes=60`
Cost breakdown by capability.

### `GET /api/v1/analytics/latency?window_minutes=60`
Latency percentiles (p50, p90, p95, p99).

### `GET /api/v1/analytics/throughput?window_minutes=60`
Events-per-minute throughput time series.

## Providers

### `GET /api/v1/providers`
List configured LLM providers with health + cost.

### `GET /api/v1/models`
List available models across all providers.

### `GET /api/v1/costs`
Cost analytics across providers.

## Plugins

### `GET /api/v1/plugins`
List installed plugins.

### `POST /api/v1/plugins/{name}/enable|disable`
Enable or disable a plugin.

## Audit

### `GET /api/v1/audit`
Query the audit log. Supports filtering by actor, action, time range.

### `GET /api/v1/audit/verify`
Verify the audit log's hash chain integrity.

## Approvals

### `GET /api/v1/approvals`
List pending approval requests.

### `POST /api/v1/approvals/{id}/respond`
Respond to an approval (approved/denied/modified).

## WebSocket

### `WS /ws/events`
Live event stream. Subscribes to all events published on the bus.

### `WS /ws/logs`
Live log stream.

## Interactive Docs

- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`
