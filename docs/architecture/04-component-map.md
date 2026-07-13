# 04 — Component Map

> **Audience:** implementers and reviewers.
> **Purpose:** complete inventory of every named component. Each entry: **responsibility**, **layer**, **owns**, **depends on**, **exposes**, **failure modes**. Claude Code and Hermes appear only as **example implementations** of their agent types — never as architectural dependencies.

---

## L1 — Kernel

### 4.1 Event Bus
- **Responsibility:** in-process async pub/sub with optional Redis adapter.
- **Owns:** topic registry, subscriber table, per-stream sequence counter, event buffer.
- **Depends on:** nothing.
- **Exposes:** `publish(event)`, `subscribe(topic, handler)`, `replay(stream_id, from_seq)`.
- **Failure modes:** subscriber throws → caught, logged, retried once; persistent store unavailable → bus blocks (fail-closed) to preserve INV-04.

### 4.2 State Manager
- **Responsibility:** event-sourced state for all aggregates (`Task`, `Agent`, `Workflow`, `MemoryScope`, `Plugin`, `User`, `ApprovalGate`).
- **Owns:** event store (Postgres/SQLite), snapshot store, in-memory cache, reducer registry.
- **Depends on:** Event Bus, Configuration Manager.
- **Exposes:** `get(aggregate_id)`, `apply(event)`, `snapshot(aggregate_id)`, `replay(aggregate_id, to_seq)`.
- **Failure modes:** reducer throws → event rejected, task paused; snapshot corrupt → fall back to full replay.

### 4.3 Configuration Manager
- **Responsibility:** load, validate, hot-reload, serve configuration.
- **Owns:** config schema, layered loader, change notifier.
- **Depends on:** Logging System.
- **Exposes:** `get(key)`, `get_typed(key, schema)`, `set(key, value)`, `watch(key, callback)`.
- **Failure modes:** schema mismatch → boot fails fast; hot-reload fails → old config kept, warning emitted.

### 4.4 Logging System
- **Responsibility:** structured JSON logging with correlation/causation IDs.
- **Owns:** formatter, stdout handler, rotating file handler, level policy.
- **Depends on:** nothing.
- **Exposes:** `logger = get_logger(__name__)`, `logger.bind(**context)`.
- **Failure modes:** disk full → fall back to stdout-only; structlog misconfigured → fail fast at boot.

### 4.5 Telemetry
- **Responsibility:** OpenTelemetry traces, metrics, logs export.
- **Owns:** OTLP exporter, in-process exporter, metric registry, span registry.
- **Depends on:** Configuration Manager.
- **Exposes:** `tracer = get_tracer(__name__)`, `counter(name)`, `histogram(name)`, `gauge(name)`.
- **Failure modes:** OTLP backend unreachable → buffer locally, retry on backoff; if buffer full, drop oldest with a counter increment.

### 4.6 Dependency Injection Container
- **Responsibility:** construct and inject all service instances at boot.
- **Owns:** provider registry, singleton cache, boot sequence.
- **Depends on:** Configuration Manager.
- **Exposes:** `container.get(Interface)`, `container.register(Interface, factory)`, `container.boot()`.
- **Failure modes:** circular dependency → boot fails with cycle report; missing provider → boot fails with the missing interface name.

### 4.7 Tool Registry
- **Responsibility:** single source of truth for tools (built-in, MCP, plugin).
- **Owns:** tool table (name, schema, handler, permission), version index.
- **Depends on:** Configuration Manager, Security Layer.
- **Exposes:** `register(tool)`, `get(name)`, `call(name, args, context)`, `list(filter)`.
- **Failure modes:** tool throws → caught, returned as structured error; tool exceeds timeout → killed, error returned.

### 4.8 Prompt Registry
- **Responsibility:** versioned, templated prompts.
- **Owns:** prompt table (name, version, template, inputs, outputs), renderer.
- **Depends on:** Configuration Manager.
- **Exposes:** `render(name, version, vars)`, `list(name)`, `diff(name, v1, v2)`.
- **Failure modes:** template syntax error → fail fast at registration; missing variable → fail at render with the variable name.

### 4.9 Gateway (the only I/O surface)
- **Responsibility:** the only package allowed to import `subprocess`, `os.open`, `socket`, `httpx`, `requests`. All I/O goes through here.
- **Owns:** fs, shell, net, process, desktop-input, clipboard sub-gateways; the sandbox policy; the egress allow-list; the audit hook.
- **Depends on:** Configuration Manager, Security Layer, Event Bus.
- **Exposes:** `gateway.fs.read/write/list/delete`, `gateway.shell.exec`, `gateway.net.request`, `gateway.process.spawn`, `gateway.desktop.input`, `gateway.clipboard.read/write`.
- **Failure modes:** permission denied → returns structured error to caller; sandbox violation → blocks, alerts, logs to audit; egress destination not in allow-list → blocks, logs.

---

## L2 — Services

### 4.10 Model Router
- **Responsibility:** route LLM calls to the right provider + model. **Agents never call providers directly — all LLM access goes through the Router.**
- **Owns:** provider registry (13 providers), per-provider health state, cost ledger, rate-limit windows, streaming multiplexer, failover policy.
- **Depends on:** Configuration Manager, Event Bus, Telemetry, Secret Manager.
- **Exposes:** `complete(request)`, `stream(request)`, `embed(texts)`, `rerank(pairs)`, `list_models(provider?)`, `get_cost_ledger()`, `get_health()`.
- **Failure modes:** provider 429 → backoff + failover; provider 5xx → failover; provider key invalid → mark unhealthy, alert user; cost budget exceeded → block non-critical calls, alert.
- **Provider support (Phase 6):** OpenAI, Anthropic, Google, OpenRouter, DeepSeek, GLM, NVIDIA, Ollama, LM Studio, Azure OpenAI, Mistral, Groq, Custom OpenAI-compatible.
- **Capabilities per provider:** multiple models, automatic failover, rate limiting, cost tracking, streaming, reasoning, vision, tool calling, context caching, priority routing, health monitoring, automatic retries.

### 4.11 Memory Manager
- **Responsibility:** unified memory API. Owns short-term, long-term, semantic, conversation, project memory; coordinates between vector store, knowledge graph, and relational store. Adds **context windows** (per-task bounded context) and **memory ranking** (relevance scoring).
- **Owns:** memory scope registry, retrieval policy, compression/summarization scheduler, context-window manager, ranking model.
- **Depends on:** Vector Memory, Knowledge Graph, Configuration Manager, Event Bus, Model Router (for embeddings and summarization).
- **Exposes:** `remember(scope, item)`, `recall(scope, query, k)`, `rank(items, query)`, `summarize(scope)`, `forget(scope, filter)`, `open_context_window(task_id, budget)`, `close_context_window(task_id)`.
- **Failure modes:** vector store down → fall back to keyword search over relational store; embedding model down → defer write, queue.

### 4.12 Vector Memory
- **Responsibility:** vector storage and similarity search (Qdrant-backed by default).
- **Owns:** Qdrant client, collection schema, index policy.
- **Depends on:** Configuration Manager.
- **Exposes:** `upsert(collection, vectors, metadata)`, `search(collection, query, k, filter)`, `delete(collection, filter)`.
- **Failure modes:** Qdrant unreachable → block writes, serve stale reads with a warning.

### 4.13 Knowledge Graph
- **Responsibility:** entity-relationship storage and graph queries (NetworkX in-process, optional Neo4j adapter).
- **Owns:** node/edge schema, traversal API, inference rules.
- **Depends on:** Configuration Manager, Model Router (for entity extraction).
- **Exposes:** `add_node(type, props)`, `add_edge(src, dst, type, props)`, `query(pattern)`, `infer(rule)`.
- **Failure modes:** inference timeout → partial results + warning; Neo4j adapter unavailable → falls back to in-process NetworkX.

### 4.14 MCP Manager
- **Responsibility:** discover, register, authenticate, monitor, hot-reload MCP (Model Context Protocol) servers.
- **Owns:** MCP server registry, per-server connection, tool/resource/prompt cache, lifecycle manager.
- **Depends on:** Configuration Manager, Event Bus, Security Layer.
- **Exposes:** `register(server_config)`, `list_servers()`, `list_tools(server_id)`, `call_tool(server_id, tool, args)`, `reload(server_id)`.
- **Failure modes:** MCP server crashes → auto-restart (max 3 in 5 min), then mark degraded; tool call timeout → killed, error returned; auth challenge → prompt user.

### 4.15 Plugin Manager
- **Responsibility:** discover, install, load, hot-reload, uninstall plugins.
- **Owns:** plugin manifest registry, plugin sandbox, plugin dependency resolver, marketplace client.
- **Depends on:** Configuration Manager, Event Bus, Security Layer, Tool Registry, Prompt Registry, **Agent Registry**.
- **Exposes:** `install(source)`, `enable(name)`, `disable(name)`, `reload(name)`, `list()`, `uninstall(name)`.
- **Failure modes:** plugin import error → plugin disabled, system continues; plugin throws at runtime → caught, isolated, plugin marked degraded; plugin violates sandbox → blocked, plugin disabled, alert.

### 4.16 Security Layer
- **Responsibility:** single entry point for all permission checks, secret access, and audit. Adds **secret rotation** and **least-privilege enforcement**.
- **Owns:** policy engine, secret store (encrypted, rotatable), audit log (hash-chained), RBAC table, least-privilege analyzer.
- **Depends on:** Configuration Manager, Event Bus, State Manager.
- **Exposes:** `check_permission(actor, action, resource)`, `approve(action, scope)`, `get_secret(name)`, `rotate_secret(name)`, `audit(event)`, `analyze_least_privilege(agent_id)`.
- **Failure modes:** policy engine unavailable → fail-closed; secret store locked → boot fails fast; audit log full → system pauses, alerts; rotation fails → old secret kept, alert.

### 4.17 Permission Manager
- **Responsibility:** interactive permission approval flow. Surfaces approval requests to the user; tracks responses and delegations.
- **Owns:** pending-approval queue, approval policy (always-ask / ask-once / never-ask), delegation table, notification dispatcher.
- **Depends on:** Security Layer, Event Bus.
- **Exposes:** `request(agent, action, resource)`, `respond(approval_id, decision)`, `delegate(agent, action_class, scope)`, `revoke_delegation(id)`.
- **Failure modes:** user does not respond → task paused, not failed; conflicting delegations → most restrictive wins.

### 4.18 Agent Registry
- **Responsibility:** single source of truth for "which agents exist and what can they do." **Capability-based, not name-based.** Claude Code and Hermes are entries here, not architectural pillars.
- **Owns:** agent table (agent_id, manifest, instance ref, health state, track record), capability index, dependency graph, version index.
- **Depends on:** Configuration Manager, Event Bus, State Manager, Telemetry.
- **Exposes:** `register(agent)`, `unregister(agent_id)`, `get(agent_id)`, `list(filter)`, `find_by_capability(cap)`, `enable/disable/reload(agent_id)`, `heartbeat()`.
- **Failure modes:** agent fails to initialize → not registered, alert; health check times out → mark degraded; multiple agents same ID + version → second registration rejected.

---

## L3 — Agents (types and example implementations)

Every agent implements `GenericAgent` (see `02-generic-agent-runtime.md`). Below: each of the 16 types, with example implementations.

### 4.19 SupervisorAgent (type)
- **Role:** orchestrator-in-chief; owns task lifecycle.
- **Type-specific methods:** `submit_goal(goal) -> TaskId`, `pause(task_id)`, `resume(task_id)`, `rollback(task_id, step_id)`, `override(task_id, decision)`.
- **Capabilities:** `supervise.task`, `supervise.plan`, `supervise.dispatch`, `supervise.reflect`, `supervise.correct`, `supervise.qa`.
- **Example implementations:** `DefaultSupervisor` (built-in, Phase 4). Future: alternative supervisors with different planning strategies.

### 4.20 PlannerAgent (type)
- **Role:** decompose a goal into a DAG plan.
- **Type-specific methods:** `decompose(goal, context) -> Plan`, `revise(plan, feedback) -> Plan`.
- **Capabilities:** `plan.decompose`, `plan.revise`.
- **Example implementations:** `LlmPlanner` (built-in).

### 4.21 CodingAgent (type)
- **Role:** software engineering — code, debug, refactor, test, git, terminal.
- **Type-specific methods:** `read_file`, `write_file`, `run_tests`, `git`, `shell`, `review`.
- **Capabilities:** `code.read`, `code.write`, `code.refactor`, `code.review`, `test.run`, `git.*`, `shell.execute`.
- **Example implementations:**
  - **`ClaudeCodeCodingAgent`** (Phase 7) — wraps the official `claude` CLI via subprocess + JSON-RPC.
  - *Future:* `OpenHandsCodingAgent`, `ClineCodingAgent`, `RooCodeCodingAgent`, `GeminiCliCodingAgent`, `CodexCliCodingAgent` — each a plugin that implements the same `CodingAgent` interface. The Supervisor treats them identically.

### 4.22 DesktopAgent (type)
- **Role:** desktop automation — UI, mouse, keyboard, browser, OCR, screenshots, app control, filesystem.
- **Type-specific methods:** `open_app`, `close_app`, `click`, `type_text`, `screenshot`, `ocr`, `find_element`, `manage_file`.
- **Capabilities:** `desktop.ui.*`, `desktop.input.*`, `desktop.screen.*`, `desktop.app.*`, `desktop.file.*`, `browser.*`.
- **Example implementations:**
  - **`HermesDesktopAgent`** (Phase 8) — wraps the in-house `hermes` daemon (Python + Playwright + PyAutoGUI).
  - *Future:* `AutoHotkeyDesktopAgent`, `PywinautoDesktopAgent` — same interface, different automation backend.

### 4.23 ResearchAgent (type)
- **Role:** web research — search, fetch, summarize, cite.
- **Capabilities:** `web.search`, `web.fetch`, `web.summarize`, `cite.format`.
- **Example implementations:** `DefaultResearchAgent` (uses Model Router + web search API).

### 4.24 BrowserAgent (type)
- **Role:** interactive web — navigate, click, input, extract, screenshot.
- **Capabilities:** `browser.navigate`, `browser.click`, `browser.input`, `browser.extract`, `browser.screenshot`.
- **Example implementations:** `PlaywrightBrowserAgent`.

### 4.25 MemoryAgent (type)
- **Role:** memory operations — recall, summarize, forget, link, rank.
- **Capabilities:** `memory.recall`, `memory.summarize`, `memory.forget`, `memory.link`, `memory.rank`.
- **Example implementations:** `DefaultMemoryAgent` (wraps Memory Manager).

### 4.26 ReflectionAgent (type)
- **Role:** critique an agent output.
- **Capabilities:** `reflect.critique`.
- **Example implementations:** `DefaultReflectionAgent` (small/cheap LLM via Model Router).

### 4.27 QAAgent (type)
- **Role:** validate a deliverable against a success criterion.
- **Capabilities:** `qa.validate`, `qa.lint`, `qa.test`, `qa.schema`.
- **Example implementations:** `DefaultQAAgent` (deterministic + LLM hybrid).

### 4.28 SecurityAgent (type)
- **Role:** security analysis — scan, audit, review.
- **Capabilities:** `security.scan`, `security.audit`, `security.review`.
- **Example implementations:** `BanditSecurityAgent`, `GitleaksSecurityAgent`, `TrivySecurityAgent` (each wraps a tool).

### 4.29 DeploymentAgent (type)
- **Role:** build, push, release, rollback.
- **Capabilities:** `deploy.build`, `deploy.push`, `deploy.release`, `deploy.rollback`.
- **Example implementations:** `DockerDeploymentAgent`, `HelmDeploymentAgent`, `WindowsServiceDeploymentAgent`.

### 4.30 VisionAgent (type)
- **Role:** image/video analysis — caption, detect, OCR, compare.
- **Capabilities:** `vision.caption`, `vision.detect`, `vision.ocr`, `vision.compare`.
- **Example implementations:** `DefaultVisionAgent` (vision-capable LLM via Model Router).

### 4.31 VoiceAgent (type)
- **Role:** STT + TTS.
- **Capabilities:** `voice.stt`, `voice.tts`.
- **Example implementations:** *Stub in v1; implementations added as plugins post-v1.*

### 4.32 DocumentAgent (type)
- **Role:** document operations — create, edit, convert, extract (PDF/DOCX/XLSX/PPTX).
- **Capabilities:** `doc.create`, `doc.edit`, `doc.convert`, `doc.extract`.
- **Example implementations:** `PdfDocumentAgent`, `DocxDocumentAgent`, `XlsxDocumentAgent`, `PptxDocumentAgent`.

### 4.33 WorkflowAgent (type)
- **Role:** execute saved workflows as a single agent call.
- **Capabilities:** `workflow.run`, `workflow.validate`.
- **Example implementations:** `DefaultWorkflowAgent` (wraps the Workflow Engine).

### 4.34 CustomAgent (type)
- **Role:** anything plugin-provided. Advertises any `custom.*` capability namespace.
- **Example implementations:** user-defined via the Plugin SDK.

---

## L4 — Supervision & Orchestration

### 4.35 SupervisorAgent (the runtime instance)
- **Responsibility:** the active supervisor instance that owns the task lifecycle.
- **Owns:** active task table, per-task state machine, step queue (per task).
- **Depends on:** PlannerAgent (via registry), ReflectionAgent, QAAgent, Agent Registry, Task Orchestrator, Memory Manager, Security Layer, Event Bus, State Manager.
- **Exposes:** `submit_goal(goal)`, `pause(task_id)`, `resume(task_id)`, `rollback(task_id, step_id)`, `override(task_id, decision)`.
- **Failure modes:** supervisor crash → restarted by process manager, state recovered from event log + checkpoints; deadlock (no agent can handle a step) → task paused, user notified.

### 4.36 Task Orchestrator
- **Responsibility:** the execution infrastructure. Owns queue, DAG, parallelism, retries, checkpointing, resume, cancellation, scheduling, background workers, approval gates.
- **Owns:** priority task queue, workflow runtime, retry policy table, checkpoint store, scheduler, background worker pool, approval gate manager.
- **Depends on:** Agent Registry, State Manager, Event Bus, Configuration Manager, Permission Manager.
- **Exposes:** `submit(plan)`, `cancel(task_id)`, `pause(task_id)`, `resume(task_id)`, `rollback(task_id, step_id)`, `schedule(task, cron)`, `submit_background(work)`.
- **Failure modes:** checkpoint write fails → step fails (does not commit); scheduler misses a tick → catches up on next tick; worker pool exhausted → queues with backpressure.

### 4.37 Workflow Engine (sub-component of Orchestrator)
- **Responsibility:** execute saved, reusable workflows.
- **Owns:** workflow definition store, workflow runtime, step transition table.
- **Depends on:** Task Orchestrator (for execution), Agent Registry (for dispatch).
- **Exposes:** `run(workflow_id, inputs)`, `list()`, `save(definition)`, `version(workflow_id)`.
- **Failure modes:** workflow step fails → per-step retry policy, then pause; workflow definition invalid → fails at save time, not run time.

### 4.38 Capability Selector (sub-component of Supervisor)
- **Responsibility:** given a step with a capability requirement, pick the best agent from the registry.
- **Owns:** scoring function (track record 40%, load 20%, cost 20%, latency 15%, user preference 5%), user preference table.
- **Depends on:** Agent Registry, Memory Manager (track records).
- **Exposes:** `select(step) -> AgentId`.
- **Failure modes:** no agent has the capability → returns `NoCandidateError`, supervisor pauses task; all candidates unhealthy → same.

---

## L5 — Surfaces

### 4.39 CLI
- **Responsibility:** terminal interface for submitting goals, inspecting tasks, managing agents/plugins/memory.
- **Stack:** Typer + Rich.
- **Depends on:** API Server (or in-process supervisor in single-binary mode).
- **Exposes:** `aaios run <goal>`, `aaios tasks`, `aaios agents`, `aaios plugins`, `aaios memory`, `aaios config`, `aaios logs`, `aaios doctor`.

### 4.40 Web UI (Dashboard)
- **Responsibility:** primary operator surface — task submission, agent monitor (shows all registered agents with health/track record/cost), live logs, memory explorer, workflow builder, prompt library, plugin marketplace, model/provider dashboards, RBAC settings, telemetry, audit log viewer.
- **Stack:** Next.js 16, React 19, Tailwind 4, shadcn/ui. Server Components for data; Client Components for interactivity. WebSocket for live updates.
- **Depends on:** API Server (REST + WebSocket).
- **Exposes:** every dashboard surface listed in the brief.

### 4.41 Desktop App
- **Responsibility:** native shell — wraps the Web UI in a Tauri window, adds native notifications (Windows toast), tray icon, and the Hermes launcher.
- **Stack:** Tauri (Rust + WebView2 on Windows) wrapping the Next.js build.
- **Depends on:** Web UI build, Hermes daemon (if desktop automation is enabled).

### 4.42 API Server
- **Responsibility:** the REST + WebSocket API. Single network entry point for all surfaces.
- **Stack:** FastAPI + Uvicorn + WebSocket.
- **Depends on:** Supervisor, Task Orchestrator, Agent Registry, Memory Manager, Plugin Manager, Security Layer.
- **Exposes:** `/api/v1/tasks`, `/api/v1/agents` (list registered agents, capabilities, health), `/api/v1/memory`, `/api/v1/plugins`, `/api/v1/providers`, `/api/v1/workflows`, `/api/v1/prompts`, `/api/v1/audit`, `/api/v1/approvals`, `/ws/events`, `/ws/logs`, `/healthz`, `/readyz`, `/metrics`.

---

## Cross-cutting stores

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
| **Agent registry** | Agent Registry (L2) | **L4 (Capability Selector), L5 (dashboard)** |
| Checkpoint store | Task Orchestrator (L4) | L4 |
| Approval queue | Permission Manager (L2) | L4, L5 |
| Track record | Memory Manager (L2) | L4 (Capability Selector) |

This concludes the component map. For runtime behavior, see [`05-data-flow.md`](05-data-flow.md).
