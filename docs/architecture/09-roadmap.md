# 09 — Roadmap

> **Audience:** all stakeholders.
> **Purpose:** the 14-phase build plan. Each phase has explicit entry criteria, exit criteria, deliverables, and approval gates. **Restructured around the Generic Agent Runtime** — the runtime comes first, then specific agent implementations are added as plugins on top.

---

## Build philosophy

We build phase-by-phase. Each phase is a self-contained chunk of work that produces a verifiable artifact. We do not move to the next phase until the current one is approved. We do not produce placeholder code. Every file in every phase is production-ready and tested.

If a better architecture emerges during a phase, we stop, document the proposed change, refactor, and resume — we do not "fix it later."

## Phase overview

| # | Phase | Effort | Status |
|---|-------|--------|--------|
| 1 | Architecture | ~1 session | ✅ In review (refactored) |
| 2 | Repository structure | ~0.5 session | ⏳ Pending approval |
| 3 | Core framework (kernel) | ~3 sessions | ⏳ Pending |
| 4 | Generic Agent Runtime + Agent Registry | ~2 sessions | ⏳ Pending |
| 5 | Task Orchestrator | ~2 sessions | ⏳ Pending |
| 6 | Model Router | ~2 sessions | ⏳ Pending |
| 7 | Memory subsystem | ~2 sessions | ⏳ Pending |
| 8 | Supervisor + Planner + Reflection + QA | ~2 sessions | ⏳ Pending |
| 9 | First CodingAgent (Claude Code) | ~1.5 sessions | ⏳ Pending |
| 10 | First DesktopAgent (Hermes) | ~2 sessions | ⏳ Pending |
| 11 | Plugins + MCP + Plugin/Agent SDK | ~2 sessions | ⏳ Pending |
| 12 | Dashboard + CLI + API | ~3 sessions | ⏳ Pending |
| 13 | Testing matrix | ~2 sessions | ⏳ Pending |
| 14 | Windows deployment + CI/CD + v1.0.0 release | ~1.5 sessions | ⏳ Pending |

Total: ~25 sessions. The phase count grew from 12 to 14 because the Generic Agent Runtime and the Task Orchestrator now have their own dedicated phases (they were previously folded into "Core framework" and "Supervisor").

---

## Phase 1 — Architecture (this phase, refactored)

### Entry criteria
- Tech stack confirmed.
- Generic Agent Runtime principle agreed.
- Windows-first principle agreed.

### Deliverables
- `README.md` (initial)
- `LICENSE` (Apache 2.0)
- `.gitignore`
- `docs/architecture/00-overview.md` through `09-roadmap.md` (10 documents)
- New in this refactor: `02-generic-agent-runtime.md` (the centerpiece design doc)

### Exit criteria
- User approves the refactored architecture in writing.

### Approval gate
**User must reply with "approved" (or with requested changes) before Phase 2 begins.**

---

## Phase 2 — Repository structure

### Entry criteria
- Phase 1 approved.

### Deliverables
- Monorepo layout: `core/`, `services/`, `agents/` (with `_types/` for interfaces, `_impls/` for built-in implementations), `supervisor/`, `orchestrator/`, `surfaces/`, `plugins/`, `docs/`, `tests/`, `deploy/windows/`, `deploy/docker/`, `scripts/`.
- `pyproject.toml` (Hatch backend, ruff config, mypy config, pytest config, Windows-specific deps).
- `package.json` (pnpm workspace, Next.js 16 init).
- `Dockerfile` (multi-stage, runtime + web) — for the optional Docker path.
- `docker-compose.yml` (the secondary deployment path).
- Windows installer scaffolding (`deploy/windows/aaios.iss` for Inno Setup).
- `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `SECURITY.md`.
- `CHANGELOG.md` (initialized, Keep-a-Changelog format).
- GitHub: `.github/issue-templates/`, `.github/pull_request_template.md`, `.github/workflows/ci.yml` (lint + test on **windows-latest AND ubuntu-latest**), `.github/workflows/release.yml`, `.github/CODEOWNERS`.
- Branch protection rules documented.
- `Makefile` / `tasks.ps1` for common commands (`tasks dev`, `tasks test`, `tasks lint`, `tasks build`, `tasks install-windows`).

### Exit criteria
- `git init` complete, first commit on `main`.
- `tasks dev` brings up the Windows-native stack (services start, even if they are stubs).
- CI passes on both `windows-latest` and `ubuntu-latest`.
- Repo pushed to `github.com/rachidSabah/aaios` (using a session-scoped `GH_TOKEN`, never committed).

### Approval gate
User confirms the repo is correctly structured and CI is green on Windows.

---

## Phase 3 — Core framework (kernel)

### Entry criteria
- Phase 2 approved.

### Deliverables
- `core/event_bus/` — typed pub/sub, in-process + optional Redis adapter, event store persistence.
- `core/state/` — event-sourced state manager, snapshot store, reducer registry.
- `core/config/` — layered loader, hot-reload, schema validation.
- `core/logging/` — structlog JSON logging, correlation IDs.
- `core/telemetry/` — OpenTelemetry SDK wiring, in-process exporter.
- `core/di/` — typed DI container, boot sequence.
- `core/registry/tool_registry.py` — tool registration, schema validation, call dispatch.
- `core/registry/prompt_registry.py` — versioned prompts, Jinja2 rendering.
- `core/gateway/` — the only package allowed to import `subprocess`, `open`, `httpx`, `socket`. Filesystem, network, shell, process, desktop-input, clipboard sub-gateways. **Windows adapter (Job Objects, ACLs, named pipes) complete; Linux adapter stubbed.**
- `core/platform/` — `windows.py` (complete), `linux.py` (stubbed for v1.1).
- `core/contracts/` — all Pydantic models and Protocol definitions shared across the system.
- Unit tests for every component (≥85% coverage), running on Windows.

### Exit criteria
- `pytest core/` passes on Windows with ≥85% coverage.
- `mypy core/` passes with no errors.
- `ruff check core/` passes.
- The kernel can boot standalone on Windows.

### Approval gate
User confirms the kernel is correct.

---

## Phase 4 — Generic Agent Runtime + Agent Registry

### Entry criteria
- Phase 3 approved.

### Deliverables
- `agents/_types/generic.py` — the `GenericAgent` Protocol with the 11 methods (`initialize`, `shutdown`, `discover_capabilities`, `execute_task`, `stream_progress`, `cancel_task`, `report_health`, `report_metrics`, `request_permission`, `serialize_state`, `restore_state`).
- `agents/_types/` — the 16 type-specific Protocols extending `GenericAgent`: `supervisor.py`, `planner.py`, `coding.py`, `desktop.py`, `research.py`, `browser.py`, `memory.py`, `reflection.py`, `qa.py`, `security.py`, `deployment.py`, `vision.py`, `voice.py`, `document.py`, `workflow.py`, `custom.py`.
- `agents/_base/` — base classes for the 3 implementation styles: `in_process.py`, `subprocess_bridge.py`, `remote_service.py`.
- `services/agent_registry/` — the Agent Registry service:
  - Discovery via entry points + plugin manifests.
  - Capability index (`cap -> [agent_id]`).
  - Health monitoring (heartbeat every 10s).
  - Lifecycle (register, unregister, enable, disable, hot-reload with parallel-old-new transition).
  - Versioning (multiple versions of same agent coexist).
  - Dependency resolution (DAG, no cycles).
- `services/agent_registry/capability_manifest.py` — `CapabilityManifest`, `Capability`, `ResourceRequirements`, `HealthCheckSpec` Pydantic models.
- A mock agent implementation (`agents/_impls/mock_agent.py`) for testing the registry without any real LLM calls.
- Integration tests with the mock agent.

### Exit criteria
- A mock agent can be registered, discovered by capability, dispatched, health-checked, hot-reloaded, and uninstalled.
- All GenericAgent interface methods are tested with the mock.
- Tests pass on Windows.

### Approval gate
User confirms the runtime and registry work.

---

## Phase 5 — Task Orchestrator

### Entry criteria
- Phase 4 approved.

### Deliverables
- `orchestrator/queue.py` — priority task queue (5 levels, aging).
- `orchestrator/dag.py` — DAG parser, validator (no cycles), executor (`asyncio.gather` for parallel steps).
- `orchestrator/retry.py` — retry policy engine (exponential backoff, retryable/non-retryable error classification).
- `orchestrator/checkpoint.py` — checkpoint writer (State Manager), checkpoint restorer.
- `orchestrator/resume.py` — crash recovery: load latest checkpoint, restore agent states, re-evaluate DAG.
- `orchestrator/cancel.py` — cooperative cancellation (`agent.cancel_task`), cascade cancellation for child tasks.
- `orchestrator/scheduler.py` — recurring and delayed tasks; Windows Task Scheduler adapter (`schtasks` / COM API) for durability; in-process cache.
- `orchestrator/workers.py` — background worker pool (`ProcessPoolExecutor` on Windows, spawn semantics).
- `orchestrator/approval_gates.py` — pre-step, post-step, pre-commit approval gates; integration with Permission Manager.
- `orchestrator/workflow_engine.py` — workflow definition parser, runtime, versioning.
- Integration tests with mock agents exercising the full lifecycle.

### Exit criteria
- A plan (DAG) can be submitted, executed (with parallel steps), checkpointed, cancelled, resumed after a simulated crash.
- Approval gates pause execution correctly.
- Scheduled tasks survive a service restart (persisted to Task Scheduler).
- Tests pass on Windows.

### Approval gate
User confirms the Orchestrator works.

---

## Phase 6 — Model Router

### Entry criteria
- Phase 5 approved.

### Deliverables
- `services/model_router/router.py` — the router itself.
- `services/model_router/providers/` — one adapter per provider (13 total):
  - `openai.py`, `anthropic.py`, `google.py`, `openrouter.py`, `deepseek.py`, `glm.py`, `nvidia.py`, `ollama.py`, `lmstudio.py`, `azure_openai.py`, `mistral.py`, `groq.py`, `custom.py`.
- `services/model_router/health.py` — per-provider health monitoring.
- `services/model_router/cost.py` — cost ledger, per-task and per-user cost tracking.
- `services/model_router/rate_limit.py` — per-provider rate limiting.
- `services/model_router/streaming.py` — streaming multiplexer.
- `services/model_router/failover.py` — automatic failover policy.
- `services/model_router/caching.py` — context caching (prompt caching for Anthropic, implicit caching for OpenAI, etc.).
- `services/model_router/reasoning.py` — reasoning model selection (route to o1 / Claude Thinking / DeepSeek-R1 when the task declares `requires_reasoning`).
- Integration tests with mocked provider responses (no real API calls in CI).

### Exit criteria
- A user can configure one or more providers and route a completion request.
- Failover works when a mocked provider returns 5xx.
- Cost is tracked per call.
- Streaming works end-to-end.
- Tests pass on Windows with no network.

### Approval gate
User confirms the Model Router works (live test with one real provider optional).

---

## Phase 7 — Memory subsystem

### Entry criteria
- Phase 6 approved.

### Deliverables
- `services/memory/manager.py` — Memory Manager, unified API.
- `services/memory/scopes.py` — short-term, long-term, semantic, conversation, project.
- `services/memory/vector.py` — Vector Memory (Qdrant adapter).
- `services/memory/graph.py` — Knowledge Graph (NetworkX default, Neo4j adapter stub).
- `services/memory/embeddings.py` — embeddings (OpenAI + sentence-transformers for local).
- `services/memory/compression.py` — memory compression + summarization scheduler.
- `services/memory/ranking.py` — relevance ranking (cross-encoder rerank + graph topology boost).
- `services/memory/context_window.py` — per-task bounded context window manager.
- `services/memory/rag.py` — RAG retrieval pipeline (hybrid vector + graph + rerank + context-window budgeting).
- Migration: Alembic schema for memory tables.
- Integration tests with Qdrant running as a Windows Service.

### Exit criteria
- A user can `remember(scope, item)`, `recall(scope, query)`, `rank(items, query)`, `summarize(scope)`, `forget(scope, filter)`, `open_context_window(task_id, budget)`, `close_context_window(task_id)`.
- RAG retrieval returns relevant chunks with citations, within token budget.
- All memory tests pass on Windows.

### Approval gate
User confirms the memory subsystem works.

---

## Phase 8 — Supervisor + Planner + Reflection + QA

### Entry criteria
- Phase 7 approved.

### Deliverables
- `supervisor/agent.py` — `DefaultSupervisor` (implements `SupervisorAgent`).
- `supervisor/capability_selector.py` — the scoring function (track record 40%, load 20%, cost 20%, latency 15%, user preference 5%).
- `agents/_impls/planner_agent.py` — `LlmPlanner` (implements `PlannerAgent`).
- `agents/_impls/reflection_agent.py` — `DefaultReflectionAgent`.
- `agents/_impls/qa_agent.py` — `DefaultQAAgent` (deterministic + LLM hybrid).
- `agents/_impls/security_agent.py` — basic SecurityAgent (wraps `bandit` and `gitleaks`).
- `agents/_impls/workflow_agent.py` — `DefaultWorkflowAgent` (wraps Workflow Engine).
- `supervisor/state_machine.py` — per-task FSM.
- Integration tests with mock CodingAgent/DesktopAgent implementations.

### Exit criteria
- A user can submit a goal via a Python REPL or CLI stub, and the supervisor will plan (DAG), dispatch (to mock agents via the Capability Selector), reflect, correct, and QA. The full task lifecycle is observable on the event bus.
- Checkpoints are written and a simulated crash resumes correctly.

### Approval gate
User confirms the supervisor loop is correct.

---

## Phase 9 — First CodingAgent implementation (Claude Code)

### Entry criteria
- Phase 8 approved.

### Deliverables
- `agents/_impls/claude_code/` — the Claude Code CodingAgent:
  - `bridge.py` — subprocess bridge to the `claude` CLI on Windows (`CreateProcess`, Job Object assignment).
  - `protocol.py` — JSON-RPC protocol definition.
  - `capabilities.py` — capability manifest (`code.read`, `code.write`, `code.refactor`, `code.review`, `test.run`, `git.*`, `shell.execute`).
  - `sandbox.py` — Windows filesystem sandbox (Gateway-mediated, restricted token, project-scope).
  - `permissions.py` — permission profile.
- `agents/_impls/claude_code/install.ps1` — installs the `claude` CLI if not present.
- Integration tests with a mocked `claude` CLI (a stub PowerShell script).

### Exit criteria
- A supervisor can dispatch a coding step to the Claude Code CodingAgent via the Capability Selector.
- Claude Code's tool calls are visible on the event bus and permission-gated.
- Tests pass with the mock CLI.

### Approval gate
User confirms Claude Code integration works (live test with real `claude` CLI optional).

**Important:** Future CodingAgent implementations (OpenHands, Cline, Roo Code, Gemini CLI, Codex CLI) will be added in Phase 11 (Plugins) or post-v1. The architecture requires zero changes to add them.

---

## Phase 10 — First DesktopAgent implementation (Hermes)

### Entry criteria
- Phase 9 approved.

### Deliverables
- `agents/_impls/hermes/` — the Hermes DesktopAgent:
  - `daemon.py` — the Hermes daemon (Python + Playwright + PyAutoGUI + Pywinauto).
  - `bridge.py` — subprocess bridge from supervisor to Hermes.
  - `protocol.py` — JSON-RPC protocol definition.
  - `capabilities.py` — UI, browser, file, app, input, screen capabilities.
  - `ocr.py` — OCR (Tesseract on Windows).
  - `screenshots.py` — screenshot capture.
- Integration tests with a headless virtual desktop (Windows built-in `Session 0` isolation, or Pywinaute's mock mode).

### Exit criteria
- A supervisor can dispatch a desktop step to the Hermes DesktopAgent via the Capability Selector.
- Hermes can open a browser, navigate, take a screenshot, extract text.
- Per-task approval gate works (user must approve desktop control).
- Tests pass on Windows.

### Approval gate
User confirms Hermes integration works.

---

## Phase 11 — Plugins + MCP + Plugin/Agent SDK

### Entry criteria
- Phase 10 approved.

### Deliverables
- `services/plugin/manager.py` — Plugin Manager.
- `services/plugin/sandbox.py` — plugin sandbox (restricted Python `__builtins__` + Job Objects on Windows).
- `services/plugin/marketplace.py` — marketplace client (verified signatures).
- `services/plugin/sdk/` — the Plugin SDK (typed interfaces, examples, test harness).
- `services/agent_sdk/` — the Agent SDK (a thin wrapper around `agents/_types/` with templates and a `cookiecutter`-style scaffolding command: `aaios sdk new-agent`).
- `services/mcp/manager.py` — MCP Manager.
- `services/mcp/lifecycle.py` — server lifecycle (discover, register, authenticate, monitor, hot-reload).
- `services/mcp/protocol.py` — MCP protocol implementation.
- Example plugins:
  - `plugins/examples/weather/` — a simple tool plugin.
  - `plugins/examples/openhands-agent/` — a CodingAgent plugin scaffold (showing how to wrap a future agent behind `GenericAgent`).
  - `plugins/examples/calculator/` — a tool plugin.
- Example MCP server configs: `config/mcp-servers/`.
- Integration tests with example plugins and a mock MCP server.

### Exit criteria
- A user can `aaios plugins install` a plugin from a local path or the marketplace.
- Plugins are hot-loaded; agents and tools appear in their respective registries immediately.
- MCP servers are discoverable and their tools are callable.
- The Agent SDK scaffolding command produces a working agent plugin template.
- All tests pass on Windows.

### Approval gate
User confirms the plugin, MCP, and SDK systems work.

---

## Phase 12 — Dashboard + CLI + API

### Entry criteria
- Phase 11 approved.

### Deliverables
- `surfaces/api/` — FastAPI server, all REST + WebSocket endpoints.
- `surfaces/cli/` — Typer-based CLI, all commands including `aaios doctor`, `aaios agents`, `aaios plugins`, `aaios service install` (Windows Service registration).
- `surfaces/web/` — Next.js 16 dashboard:
  - Pages: dashboard (overview), tasks, agents (shows all registered agents with health/track record/cost — capability-indexed, not name-indexed), memory, plugins, marketplace, providers, models, workflows, prompts, logs, audit, approvals, telemetry, settings.
  - Components: task monitor, agent monitor (live), capability selector inspector, live log viewer, workflow builder (drag-and-drop DAG), prompt library, memory explorer, plugin marketplace, RBAC settings, telemetry charts, approval gate queue, least-privilege report, secret rotation UI.
  - Dark mode + light mode.
  - Responsive (desktop + tablet).
  - Windows toast notifications via Tauri for approval gates.
- `surfaces/desktop/` — Tauri wrapper (WebView2).

### Exit criteria
- A user can submit a task from the dashboard and watch it execute in real time.
- The agent monitor shows all registered agents, indexed by capability, with health/track record/cost.
- Approval gates surface as Windows toast notifications and dashboard badges.
- CLI parity with the dashboard for common operations.
- API docs (OpenAPI) auto-generated and accurate.
- `aaios doctor` runs all health checks and produces a JSON report.

### Approval gate
User confirms the dashboard, CLI, and API are usable.

---

## Phase 13 — Testing matrix

### Entry criteria
- Phase 12 approved (testing has been continuous throughout).

### Deliverables
- Full unit test suite (≥85% coverage across the codebase, on Windows).
- Integration test suite (every service tested with real dependencies as Windows Services).
- End-to-end test suite (Playwright for the dashboard; CLI invocations for the CLI).
- Stress tests (concurrent task submission for the supervisor; queue depth for the orchestrator).
- Performance tests (benchmarks for kernel, memory, model router, capability selector; documented baselines).
- Security tests (gitleaks, bandit, pip-audit, npm audit, Trivy image scan, Windows Defender plugin scan, ACL verification).
- Mutation testing baseline (mutmut for the kernel).
- Tests running on **both** `windows-latest` and `ubuntu-latest` in CI (Linux tests may skip Windows-specific features).

### Exit criteria
- All test suites pass in CI with no network access (`pytest --offline`).
- Coverage ≥85% on Windows.
- No Critical or High vulnerabilities.
- Performance baselines documented and within budget.

### Approval gate
User confirms the test suite is comprehensive and CI is green on Windows.

---

## Phase 14 — Windows deployment + CI/CD + v1.0.0 release

### Entry criteria
- Phase 13 approved.

### Deliverables
- **Windows installer** (Inno Setup + PyInstaller): `AAiOS-Setup-x.y.z.exe`.
  - Bundles Python 3.12, Node 22, selected Python deps, Next.js build.
  - Installs PostgreSQL 16 (if not present), Qdrant, Tesseract.
  - Creates the `.\AAiOS` service account.
  - Installs all Windows Services with recovery actions.
  - Sets all file ACLs.
  - Configures Windows Defender exclusions and Controlled Folder Access.
  - Generates the master key (prompts for passphrase).
  - Runs `aaios doctor` at the end.
- **Optional Docker Compose** deployment (`docker-compose.yml` + multi-arch images on GHCR).
- **GitHub Actions**:
  - `ci.yml` — lint, type-check, test, security scan on every PR (Windows + Linux matrix).
  - `release.yml` — semantic versioning, auto-changelog, Windows installer build + signing, Docker image build and push to GHCR, GitHub Release with notes.
  - `codeql.yml` — CodeQL analysis.
  - `dependabot.yml` — dependency updates.
- Branch protection rules enforced.
- `docs/installation.md` (Windows-native first), `docs/deployment.md`, `docs/developer-guide.md`, `docs/plugin-sdk.md`, `docs/agent-sdk.md`.
- Architecture diagrams exported as PNG for the README.
- `aaios doctor` command finalized.
- **v1.0.0 release published.**

### Exit criteria
- A new Windows user can follow `docs/installation.md` and have a running system in under 30 minutes via the installer.
- The CI/CD pipeline produces a signed, scanned, v1.0.0 Windows installer.
- The repo is public on `github.com/rachidSabah/aaios` with the v1.0.0 release.

### Approval gate
User confirms v1.0.0 is ready for public release.

---

## Cross-phase invariants

Enforced continuously from Phase 2 onward:

- **No placeholder code.** Every function does what its docstring says. No `pass`, no `TODO`, no `raise NotImplementedError` in merged code (except for explicitly-stubbed Linux adapters, which are clearly labeled).
- **No untyped code.** `mypy --strict` passes on every commit.
- **No untested code.** Every public function has at least one test. Coverage ≥85%.
- **No insecure code.** `gitleaks`, `bandit`, `pip-audit`, `npm audit` all clean.
- **No undocumented code.** Every public function has a docstring. Every module has a module-level docstring.
- **No bypass of the Gateway.** Static-analysis rule prevents direct use of `subprocess`, `open`, `httpx`, `socket` outside `core/gateway/`.
- **No agent implementation leakage.** The Supervisor, Orchestrator, and Capability Selector never reference Claude Code, Hermes, or any specific implementation by name. CI enforces this with a regex ban.
- **Windows-first.** Every feature works on Windows 11 first. Linux support is additive and may lag.

## How to request changes

At any approval gate:

1. **Approve** — proceed to the next phase.
2. **Request changes** — describe what needs to change. I will revise the current phase.
3. **Request a refactor** — if a better architecture has emerged, describe it. I will document the proposed change, refactor, and resume.
4. **Pause** — work can be paused and resumed. The worklog tracks state.

---

This concludes the roadmap. Phase 1 (refactored) is now ready for review.
