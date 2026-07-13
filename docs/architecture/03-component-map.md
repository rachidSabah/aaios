# 03 — Component Map

> **Audience:** implementers and reviewers.
> **Purpose:** a complete inventory of every named component from the brief. Each entry covers: **responsibility**, **layer**, **owns**, **depends on**, **exposes**, and **key failure modes**.

---

## L1 — Kernel

### 3.1 Event Bus
- **Responsibility:** in-process async pub/sub with optional Redis adapter for multi-process.
- **Owns:** the topic registry, the subscriber table, the per-stream sequence counter, the event buffer.
- **Depends on:** nothing (it is the foundation).
- **Exposes:** `publish(event)`, `subscribe(topic, handler)`, `replay(stream_id, from_seq)`.
- **Failure modes:** subscriber throws → caught and logged, delivery retried once; persistent store unavailable → bus blocks (fail-closed) to preserve INV-04.

### 3.2 State Manager
- **Responsibility:** event-sourced state for all aggregates (Task, Agent, Workflow, MemoryScope, Plugin, User).
- **Owns:** the event store (Postgres/SQLite), the snapshot store, the in-memory cache, the reducer registry.
- **Depends on:** Event Bus, Configuration Manager.
- **Exposes:** `get(aggregate_id)`, `apply(event)`, `snapshot(aggregate_id)`, `replay(aggregate_id, to_seq)`.
- **Failure modes:** reducer throws → event rejected, task paused; snapshot corrupt → fall back to full replay.

### 3.3 Configuration Manager
- **Responsibility:** load, validate, hot-reload, and serve configuration.
- **Owns:** the config schema, the layered loader (CLI > env > .env > yaml > defaults), the change notifier.
- **Depends on:** Logging System.
- **Exposes:** `get(key)`, `get_typed(key, schema)`, `set(key, value)`, `watch(key, callback)`.
- **Failure modes:** schema mismatch → boot fails fast; hot-reload fails → old config kept, warning emitted.

### 3.4 Logging System
- **Responsibility:** structured JSON logging with correlation/causation IDs.
- **Owns:** the log formatter, the stdout handler, the rotating file handler, the log level policy.
- **Depends on:** nothing.
- **Exposes:** `logger = get_logger(__name__)`, `logger.bind(**context)`.
- **Failure modes:** disk full → fall back to stdout-only; structlog misconfigured → fail fast at boot.

### 3.5 Telemetry
- **Responsibility:** OpenTelemetry traces, metrics, logs export.
- **Owns:** the OTLP exporter, the in-process exporter, the metric registry, the span registry.
- **Depends on:** Configuration Manager.
- **Exposes:** `tracer = get_tracer(__name__)`, `counter(name)`, `histogram(name)`, `gauge(name)`.
- **Failure modes:** OTLP backend unreachable → buffer locally, retry on backoff; if buffer full, drop oldest with a counter increment.

### 3.6 Dependency Injection Container
- **Responsibility:** construct and inject all service instances at boot.
- **Owns:** the provider registry, the singleton cache, the boot sequence.
- **Depends on:** Configuration Manager.
- **Exposes:** `container.get(Interface)`, `container.register(Interface, factory)`, `container.boot()`.
- **Failure modes:** circular dependency → boot fails with a clear cycle report; missing provider → boot fails with the missing interface name.

### 3.7 Tool Registry
- **Responsibility:** the single source of truth for tools (built-in, MCP, plugin).
- **Owns:** the tool table (name, schema, handler, permission), the tool version index.
- **Depends on:** Configuration Manager, Security Layer.
- **Exposes:** `register(tool)`, `get(name)`, `call(name, args, context)`, `list(filter)`.
- **Failure modes:** tool throws → caught, returned as a structured error to the agent; tool exceeds timeout → killed, error returned.

### 3.8 Prompt Registry
- **Responsibility:** versioned, templated prompts.
- **Owns:** the prompt table (name, version, template, inputs, outputs), the renderer.
- **Depends on:** Configuration Manager.
- **Exposes:** `render(name, version, vars)`, `list(name)`, `diff(name, v1, v2)`.
- **Failure modes:** template syntax error → fail fast at registration time; missing variable → fail at render time with the variable name.

---

## L2 — Services

### 3.9 Model Router
- **Responsibility:** route LLM calls to the right provider + model, with failover, rate limiting, cost tracking, streaming, and health monitoring.
- **Owns:** the provider registry (10+ providers), the per-provider health state, the cost ledger, the rate-limit windows, the streaming multiplexer.
- **Depends on:** Configuration Manager, Event Bus, Telemetry, Secret Manager.
- **Exposes:** `complete(request)`, `stream(request)`, `embed(texts)`, `list_models(provider?)`, `get_cost_ledger()`.
- **Failure modes:** provider 429 → backoff + failover; provider 5xx → failover; provider key invalid → mark unhealthy, alert user; cost budget exceeded → block non-critical calls, alert user.
- **Provider support (Phase 6):** OpenRouter, OpenAI, Anthropic, Google, Mistral, DeepSeek, GLM, NVIDIA, Ollama, LM Studio, Custom OpenAI-compatible.

### 3.10 Memory Manager
- **Responsibility:** the unified memory API. Owns short-term, long-term, semantic, conversation, and project memory; coordinates between vector store, knowledge graph, and relational store.
- **Owns:** the memory scope registry, the retrieval policy, the compression/summarization scheduler.
- **Depends on:** Vector Memory, Knowledge Graph, Configuration Manager, Event Bus, Model Router (for embeddings and summarization).
- **Exposes:** `remember(scope, item)`, `recall(scope, query, k)`, `summarize(scope)`, `forget(scope, filter)`.
- **Failure modes:** vector store down → fall back to keyword search over relational store; embedding model down → defer write, queue.

### 3.11 Vector Memory
- **Responsibility:** vector storage and similarity search (Qdrant-backed by default).
- **Owns:** the Qdrant client, the collection schema, the index policy.
- **Depends on:** Configuration Manager.
- **Exposes:** `upsert(collection, vectors, metadata)`, `search(collection, query, k, filter)`, `delete(collection, filter)`.
- **Failure modes:** Qdrant unreachable → block writes, serve stale reads with a warning.

### 3.12 Knowledge Graph
- **Responsibility:** entity-relationship storage and graph queries (NetworkX in-process, optional Neo4j adapter).
- **Owns:** the node/edge schema, the traversal API, the inference rules.
- **Depends on:** Configuration Manager, Model Router (for entity extraction).
- **Exposes:** `add_node(type, props)`, `add_edge(src, dst, type, props)`, `query(pattern)`, `infer(rule)`.
- **Failure modes:** inference timeout → returns partial results with a warning; Neo4j adapter unavailable → falls back to in-process NetworkX.

### 3.13 MCP Manager
- **Responsibility:** discover, register, authenticate, monitor, and hot-reload MCP (Model Context Protocol) servers.
- **Owns:** the MCP server registry, the per-server connection, the tool/resource/prompt cache, the lifecycle manager.
- **Depends on:** Configuration Manager, Event Bus, Security Layer.
- **Exposes:** `register(server_config)`, `list_servers()`, `list_tools(server_id)`, `call_tool(server_id, tool, args)`, `reload(server_id)`.
- **Failure modes:** MCP server crashes → auto-restart (max 3 in 5 min), then mark degraded; tool call timeout → killed, error returned to agent; auth challenge → prompt user.

### 3.14 Plugin Manager
- **Responsibility:** discover, install, load, hot-reload, and uninstall plugins.
- **Owns:** the plugin manifest registry, the plugin sandbox, the plugin dependency resolver, the plugin marketplace client.
- **Depends on:** Configuration Manager, Event Bus, Security Layer, Tool Registry, Prompt Registry.
- **Exposes:** `install(source)`, `enable(name)`, `disable(name)`, `reload(name)`, `list()`, `uninstall(name)`.
- **Failure modes:** plugin import error → plugin disabled, system continues; plugin throws at runtime → caught, isolated, plugin marked degraded; plugin violates sandbox → blocked, plugin disabled, alert.

### 3.15 Security Layer
- **Responsibility:** the single entry point for all permission checks, secret access, and audit.
- **Owns:** the policy engine (rego or python rules), the secret store (encrypted), the audit log, the RBAC table.
- **Depends on:** Configuration Manager, Event Bus, State Manager.
- **Exposes:** `check_permission(actor, action, resource)`, `approve(action, scope)`, `get_secret(name)`, `audit(event)`.
- **Failure modes:** policy engine unavailable → fail-closed (all actions denied); secret store locked → boot fails fast; audit log full → system pauses, alerts user.

### 3.16 Permission Manager
- **Responsibility:** the interactive permission approval flow — when an agent needs an action that requires user approval, the Permission Manager is what surfaces it to the user and tracks the response.
- **Owns:** the pending-approval queue, the approval policy (always-ask / ask-once / never-ask), the delegation table.
- **Depends on:** Security Layer, Event Bus.
- **Exposes:** `request(agent, action, resource)`, `respond(approval_id, decision)`, `delegate(agent, action_class, scope)`.
- **Failure modes:** user does not respond → task paused, not failed; conflicting delegations → most restrictive wins.

---

## L3 — Agents

Each agent follows the `Agent` protocol:

```python
class Agent(Protocol):
    name: str
    capabilities: CapabilityManifest
    async def health_check(self) -> HealthState: ...
    async def execute(self, step: Step, ctx: Context) -> StepResult: ...
    async def correct(self, step: Step, critique: str, ctx: Context) -> StepResult: ...
```

### 3.17 Claude Code (coding agent)
- **Specialty:** software engineering — write code, debug, refactor, run tests, manage git, code review.
- **Binding:** subprocess bridge to the official `claude` CLI over JSON-RPC.
- **Capabilities:** `code.write`, `code.read`, `code.refactor`, `test.run`, `git.*`, `review.*`.
- **Permissions:** filesystem (project-scoped), shell (project-scoped), git (project-scoped). Network denied by default.
- **Never:** does architecture planning (that is the Executive Planner's job), does not modify files outside the project root.

### 3.18 Hermes (desktop agent)
- **Specialty:** desktop automation — UI automation, browser automation, file management, open apps, screenshots, OCR, keyboard, mouse, system interaction.
- **Binding:** subprocess bridge to the `hermes` daemon (JSON-RPC over stdin/stdout).
- **Capabilities:** `desktop.ui.*`, `desktop.file.*`, `desktop.app.*`, `desktop.input.*`, `desktop.screen.*`, `browser.*`.
- **Permissions:** whole-desktop by default (user must opt in per-task); each high-level action goes through Permission Manager.
- **Never:** does architecture planning, does not write code (that is Claude Code's job).

### 3.19 Research Agent
- **Specialty:** web research — search, fetch, summarize, cite.
- **Capabilities:** `web.search`, `web.fetch`, `web.summarize`, `cite.format`.
- **Permissions:** network (HTTP/HTTPS only); filesystem (write to scratch only).

### 3.20 Browser Agent
- **Specialty:** interactive web — fill forms, click, extract data from rendered pages.
- **Capabilities:** `browser.navigate`, `browser.click`, `browser.input`, `browser.extract`, `browser.screenshot`.
- **Permissions:** network; headless browser sandbox; no file writes outside scratch.

### 3.21 Memory Agent
- **Specialty:** memory operations — recall, summarize, forget, link.
- **Capabilities:** `memory.recall`, `memory.summarize`, `memory.forget`, `memory.link`.
- **Permissions:** memory store read/write; no network, no filesystem.

### 3.22 Planner Agent (Executive Planner)
- **Specialty:** decompose a goal into a plan.
- **Capabilities:** `plan.decompose`, `plan.revise`.
- **Permissions:** read-only on everything; no side effects.

### 3.23 Reflection Agent
- **Specialty:** critique an agent output.
- **Capabilities:** `reflect.critique`.
- **Permissions:** read-only.

### 3.24 Self-Correction Agent
- **Specialty:** repair a rejected agent output, given the critique.
- **Capabilities:** `correct.repair`.
- **Permissions:** same as the agent it is repairing (delegated).

### 3.25 QA Agent
- **Specialty:** validate a deliverable against a success criterion.
- **Capabilities:** `qa.validate`, `qa.lint`, `qa.test`.
- **Permissions:** read-only + execute tests in a sandbox.

---

## L4 — Supervision

### 3.26 Supervisor Agent
- **Responsibility:** owns the task lifecycle; the orchestrator-in-chief.
- **Owns:** the active task table, the per-task state machine, the step queue.
- **Depends on:** Executive Planner, Agent Router, Reflection Agent, Self-Correction Agent, QA Agent, Workflow Engine, Memory Manager, Security Layer, Event Bus, State Manager.
- **Exposes:** `submit(goal)`, `pause(task_id)`, `resume(task_id)`, `rollback(task_id, step_id)`, `override(task_id, decision)`.
- **Failure modes:** supervisor crash → restarted by process manager, state recovered from event log; deadlock (no agent can handle a step) → task paused, user notified.

### 3.27 Workflow Engine
- **Responsibility:** execute saved, reusable workflows (still supervised).
- **Owns:** the workflow definition store, the workflow runtime, the step transition table.
- **Depends on:** Supervisor, Agent Router, Memory Manager.
- **Exposes:** `run(workflow_id, inputs)`, `list()`, `save(definition)`, `version(workflow_id)`.
- **Failure modes:** workflow step fails → retries per workflow policy, then pauses; workflow definition invalid → fails at save time, not run time.

---

## L5 — Surfaces

### 3.28 CLI
- **Responsibility:** terminal interface for submitting goals, inspecting tasks, managing plugins, viewing logs.
- **Stack:** Typer + Rich.
- **Depends on:** API Server (or in-process supervisor in single-binary mode).
- **Exposes:** `aaios run <goal>`, `aaios tasks`, `aaios plugins`, `aaios memory`, `aaios config`, `aaios logs`.

### 3.29 Web UI (Dashboard)
- **Responsibility:** the primary operator surface — task submission, agent monitor, live logs, memory explorer, workflow builder, prompt library, plugin marketplace, model/provider dashboards, settings.
- **Stack:** Next.js 16, React 19, Tailwind 4, shadcn/ui. Server Components for data, Client Components for interactivity. WebSocket for live updates.
- **Depends on:** API Server (REST + WebSocket).
- **Exposes:** every dashboard surface listed in the brief.

### 3.30 Desktop App
- **Responsibility:** the native shell — wraps the Web UI in a Tauri or Electron window, adds native notifications, tray icon, and the Hermes launcher.
- **Stack:** Tauri (preferred, Rust + WebView) wrapping the Next.js build.
- **Depends on:** Web UI build, Hermes daemon.

### 3.31 API Server
- **Responsibility:** the REST + WebSocket API. The single network entry point for all surfaces.
- **Stack:** FastAPI (Python) + Uvicorn + WebSocket.
- **Depends on:** Supervisor, Memory Manager, Plugin Manager, Security Layer.
- **Exposes:** `/api/v1/tasks`, `/api/v1/agents`, `/api/v1/memory`, `/api/v1/plugins`, `/api/v1/providers`, `/api/v1/workflows`, `/api/v1/prompts`, `/api/v1/audit`, `/ws/events` (live event stream), `/ws/logs` (live log stream), `/healthz`, `/readyz`, `/metrics`.

---

## Cross-cutting: registries and stores

The following stores cut across layers but are owned by a single layer each:

| Store | Owner | Used by |
|-------|-------|---------|
| Event store | State Manager (L1) | All layers |
| Snapshot store | State Manager (L1) | All layers |
| Audit log | Security Layer (L2) | All layers |
| Cost ledger | Model Router (L2) | L4, L5 |
| Memory store | Memory Manager (L2) | L3, L4 |
| Vector store | Vector Memory (L2) | L2 (Memory Manager) |
| Knowledge graph | Knowledge Graph (L2) | L2 (Memory Manager) |
| Tool registry | L1 (Tool Registry) | L2 (MCP), L3 (all agents) |
| Prompt registry | L1 (Prompt Registry) | L3, L4 |
| Plugin registry | Plugin Manager (L2) | L2, L3, L5 |
| Provider registry | Model Router (L2) | L3, L4 |
| Agent registry | Supervisor (L4) | L4 |

This concludes the component map. For the runtime behavior of these components, see [`04-data-flow.md`](04-data-flow.md).
