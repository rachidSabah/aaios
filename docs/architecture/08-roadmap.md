# 08 — Roadmap

> **Audience:** all stakeholders.
> **Purpose:** define the 12-phase build plan. Each phase has explicit entry criteria, exit criteria, deliverables, and approval gates.

---

## Build philosophy

We build phase-by-phase. Each phase is a self-contained chunk of work that produces a verifiable artifact. We do not move to the next phase until the current one is approved. We do not produce placeholder code. Every file in every phase is production-ready and tested.

If a better architecture emerges during a phase, we stop, document the proposed change, refactor, and resume — we do not "fix it later."

## Phase overview

| # | Phase | Estimated effort | Status |
|---|-------|------------------|--------|
| 1 | Architecture | ~1 session | ✅ In review |
| 2 | Repository structure | ~0.5 session | ⏳ Pending approval |
| 3 | Core framework (kernel) | ~3 sessions | ⏳ Pending |
| 4 | Supervisor | ~2 sessions | ⏳ Pending |
| 5 | Memory | ~2 sessions | ⏳ Pending |
| 6 | Model Router | ~2 sessions | ⏳ Pending |
| 7 | Claude Code integration | ~1.5 sessions | ⏳ Pending |
| 8 | Hermes integration | ~2 sessions | ⏳ Pending |
| 9 | Plugins + MCP | ~2 sessions | ⏳ Pending |
| 10 | Dashboard + CLI + API | ~3 sessions | ⏳ Pending |
| 11 | Testing | ~2 sessions | ⏳ Pending |
| 12 | Deployment + CI/CD + release | ~1.5 sessions | ⏳ Pending |

Total: ~22 sessions. A "session" is one sustained engineering block (~2-4 hours of focused work). In practice, some phases will overlap (Phase 11 testing will start during Phase 3 and continue throughout).

---

## Phase 1 — Architecture (this phase)

### Entry criteria
- Tech stack confirmed with the user.
- Security model approved at the threat-model level.

### Deliverables
- `README.md` (initial)
- `LICENSE` (Apache 2.0)
- `.gitignore`
- `docs/architecture/00-overview.md`
- `docs/architecture/01-goals-and-principles.md`
- `docs/architecture/02-system-design.md`
- `docs/architecture/03-component-map.md`
- `docs/architecture/04-data-flow.md`
- `docs/architecture/05-tech-stack.md`
- `docs/architecture/06-security-model.md`
- `docs/architecture/07-deployment-topology.md`
- `docs/architecture/08-roadmap.md` (this file)

### Exit criteria
- User approves the architecture in writing.
- No open architectural questions blocking Phase 2.

### Approval gate
**User must reply with "approved" (or with requested changes) before Phase 2 begins.**

---

## Phase 2 — Repository structure

### Entry criteria
- Phase 1 approved.

### Deliverables
- Monorepo layout: `core/`, `services/`, `agents/`, `supervisor/`, `surfaces/`, `plugins/`, `docs/`, `tests/`, `deploy/`, `scripts/`.
- `pyproject.toml` (Hatch backend, ruff config, mypy config, pytest config).
- `package.json` (pnpm workspace, Next.js 16 init).
- `Dockerfile` (multi-stage, runtime + web).
- `docker-compose.yml` (full stack, dev profile + prod profile).
- `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `SECURITY.md`.
- `CHANGELOG.md` (initialized, Keep-a-Changelog format).
- GitHub: `.github/issue-templates/` (bug, feature, plugin-idea), `.github/pull_request_template.md`, `.github/workflows/ci.yml` (lint + test skeleton), `.github/workflows/release.yml` (semantic-release skeleton), `.github/CODEOWNERS`.
- Branch protection rules documented (main: required reviews=1, required CI pass, no force push).
- `Makefile` for common commands (`make dev`, `make test`, `make lint`, `make build`).

### Exit criteria
- `git init` complete, first commit on `main`.
- `make dev` brings up the stack (services start, even if they are stubs).
- CI passes (lint + tests on an empty test suite).
- Repo pushed to `github.com/rachidSabah/aaios` (using a session-scoped `GH_TOKEN`, never committed).

### Approval gate
User confirms the repo is correctly structured and CI is green.

---

## Phase 3 — Core framework (kernel)

### Entry criteria
- Phase 2 approved.

### Deliverables
- `core/event_bus/` — typed pub/sub, in-process + Redis adapter, event store persistence.
- `core/state/` — event-sourced state manager, snapshot store, reducer registry.
- `core/config/` — layered loader, hot-reload, schema validation.
- `core/logging/` — structlog JSON logging, correlation IDs.
- `core/telemetry/` — OpenTelemetry SDK wiring, in-process exporter.
- `core/di/` — typed DI container, boot sequence.
- `core/registry/tool_registry.py` — tool registration, schema validation, call dispatch.
- `core/registry/prompt_registry.py` — versioned prompts, Jinja2 rendering.
- `core/gateway/` — the only package allowed to import `subprocess`, `open`, `httpx`, `socket`. Filesystem, network, shell gateways.
- `core/contracts/` — all Pydantic models and Protocol definitions shared across the system.
- Unit tests for every component above (≥85% coverage).

### Exit criteria
- `pytest core/` passes with ≥85% coverage.
- `mypy core/` passes with no errors.
- `ruff check core/` passes.
- The kernel can boot standalone (a `core.bootstrap` script that wires the DI container and prints "AAiOS kernel ready" to stdout).

### Approval gate
User confirms the kernel is correct and ready to be built upon.

---

## Phase 4 — Supervisor

### Entry criteria
- Phase 3 approved.

### Deliverables
- `supervisor/agent.py` — the Supervisor Agent, owns the task lifecycle.
- `supervisor/planner.py` — Executive Planner, decomposes goals.
- `supervisor/router.py` — Agent Router, selects agent for step.
- `supervisor/reflection.py` — Reflection Agent.
- `supervisor/correction.py` — Self-Correction Agent.
- `supervisor/qa.py` — QA Agent.
- `supervisor/workflow_engine.py` — Workflow Engine.
- `supervisor/state_machine.py` — task state machine (per-task FSM).
- Integration tests with a mock agent (no real LLM calls yet).

### Exit criteria
- A user can submit a goal via a Python REPL or a CLI stub, and the supervisor will plan, dispatch (to a mock agent), reflect, correct, and QA. The full task lifecycle is observable on the event bus.
- All supervisor tests pass with the mock agent.

### Approval gate
User confirms the supervisor loop is correct.

---

## Phase 5 — Memory

### Entry criteria
- Phase 4 approved.

### Deliverables
- `services/memory/manager.py` — Memory Manager, unified API.
- `services/memory/scopes.py` — short-term, long-term, semantic, conversation, project.
- `services/memory/vector.py` — Vector Memory (Qdrant adapter).
- `services/memory/graph.py` — Knowledge Graph (NetworkX default, Neo4j adapter).
- `services/memory/embeddings.py` — embeddings (OpenAI + sentence-transformers).
- `services/memory/compression.py` — memory compression + summarization scheduler.
- `services/memory/rag.py` — RAG retrieval pipeline (hybrid vector + graph + rerank).
- Migration: Alembic schema for memory tables.
- Integration tests with Qdrant running in Docker.

### Exit criteria
- A user can `remember(scope, item)`, `recall(scope, query)`, `summarize(scope)`, and `forget(scope, filter)`.
- RAG retrieval returns relevant chunks with citations.
- All memory tests pass.

### Approval gate
User confirms the memory subsystem works correctly.

---

## Phase 6 — Model Router

### Entry criteria
- Phase 5 approved.

### Deliverables
- `services/model_router/router.py` — the router itself.
- `services/model_router/providers/` — one adapter per provider:
  - `openrouter.py`, `openai.py`, `anthropic.py`, `google.py`, `mistral.py`, `deepseek.py`, `glm.py`, `nvidia.py`, `ollama.py`, `lmstudio.py`, `custom.py`.
- `services/model_router/health.py` — per-provider health monitoring.
- `services/model_router/cost.py` — cost ledger, per-task and per-user cost tracking.
- `services/model_router/rate_limit.py` — per-provider rate limiting.
- `services/model_router/streaming.py` — streaming multiplexer.
- `services/model_router/failover.py` — automatic failover policy.
- Integration tests with mocked provider responses (no real API calls in CI).

### Exit criteria
- A user can configure one or more providers and route a completion request.
- Failover works when a mocked provider returns 5xx.
- Cost is tracked per call.
- All provider tests pass with mocked responses.

### Approval gate
User confirms the Model Router works with at least one real provider (live test, optional).

---

## Phase 7 — Claude Code integration

### Entry criteria
- Phase 6 approved.

### Deliverables
- `agents/claude_code/bridge.py` — subprocess bridge to `claude` CLI.
- `agents/claude_code/protocol.py` — JSON-RPC protocol definition.
- `agents/claude_code/capabilities.py` — capability manifest.
- `agents/claude_code/sandbox.py` — `bwrap`-based filesystem sandbox.
- `agents/claude_code/permissions.py` — permission profile.
- Integration tests with a mocked `claude` CLI (a stub script).

### Exit criteria
- A supervisor can dispatch a coding step to Claude Code via the bridge.
- Claude Code's tool calls are visible on the event bus and permission-gated.
- Tests pass with the mock CLI.

### Approval gate
User confirms Claude Code integration works (live test with real `claude` CLI optional).

---

## Phase 8 — Hermes integration

### Entry criteria
- Phase 7 approved.

### Deliverables
- `agents/hermes/daemon.py` — the Hermes daemon (Python + Playwright + PyAutoGUI).
- `agents/hermes/bridge.py` — subprocess bridge from supervisor to Hermes.
- `agents/hermes/protocol.py` — JSON-RPC protocol definition.
- `agents/hermes/capabilities.py` — UI, browser, file, app, input, screen capabilities.
- `agents/hermes/ocr.py` — OCR (Tesseract).
- `agents/hermes/screenshots.py` — screenshot capture.
- Integration tests with a headless X server (Xvfb).

### Exit criteria
- A supervisor can dispatch a desktop step to Hermes.
- Hermes can open a browser, navigate, take a screenshot, extract text.
- Tests pass under Xvfb.

### Approval gate
User confirms Hermes integration works.

---

## Phase 9 — Plugins + MCP

### Entry criteria
- Phase 8 approved.

### Deliverables
- `services/plugin/manager.py` — Plugin Manager.
- `services/plugin/sandbox.py` — plugin sandbox (restricted Python + seccomp on Linux).
- `services/plugin/marketplace.py` — marketplace client (verified signatures).
- `services/plugin/sdk/` — the Plugin SDK (typed interfaces, examples).
- `services/mcp/manager.py` — MCP Manager.
- `services/mcp/lifecycle.py` — server lifecycle (discover, register, authenticate, monitor, hot-reload).
- `services/mcp/protocol.py` — MCP protocol implementation.
- Example plugins: `plugins/examples/weather/`, `plugins/examples/calculator/`.
- Example MCP server config: `config/mcp-servers/`.
- Integration tests with example plugins and a mock MCP server.

### Exit criteria
- A user can `aaios plugins install` a plugin from a local path or the marketplace.
- Plugins are hot-loaded; tools appear in the registry.
- MCP servers are discoverable and their tools are callable.
- All tests pass.

### Approval gate
User confirms the plugin and MCP systems work.

---

## Phase 10 — Dashboard + CLI + API

### Entry criteria
- Phase 9 approved.

### Deliverables
- `surfaces/api/` — FastAPI server, all REST + WebSocket endpoints.
- `surfaces/cli/` — Typer-based CLI, all commands.
- `surfaces/web/` — Next.js 16 dashboard:
  - Pages: dashboard (overview), tasks, agents, memory, plugins, marketplace, providers, models, workflows, prompts, logs, audit, settings.
  - Components: task monitor, agent monitor, live log viewer, workflow builder (drag-and-drop), prompt library, memory explorer, plugin marketplace, RBAC settings, telemetry charts.
  - Dark mode + light mode.
  - Responsive (desktop + tablet).
- `surfaces/desktop/` — Tauri wrapper (Phase 12 deliverable; stub in Phase 10).

### Exit criteria
- A user can submit a task from the dashboard and watch it execute in real time.
- All dashboard surfaces are functional.
- CLI parity with the dashboard for the common operations.
- API docs (OpenAPI) auto-generated and accurate.

### Approval gate
User confirms the dashboard, CLI, and API are usable.

---

## Phase 11 — Testing

### Entry criteria
- Phase 10 approved (though testing has been continuous throughout).

### Deliverables
- Full unit test suite (≥85% coverage across the codebase).
- Integration test suite (every service tested with its real dependencies in Docker).
- End-to-end test suite (Playwright for the dashboard; CLI invocations for the CLI).
- Stress tests (locust scripts for the API; concurrent task submission for the supervisor).
- Performance tests (benchmarks for the kernel, memory, model router; documented baselines).
- Security tests (gitleaks, bandit, pip-audit, npm audit, Trivy image scan, Snyk Code).
- Mutation testing baseline (cargo-mutants or mutmut for the kernel).

### Exit criteria
- All test suites pass in CI with no network access (`pytest --offline`).
- Coverage ≥85% across the codebase.
- No Critical or High vulnerabilities.
- Performance baselines documented and within budget.

### Approval gate
User confirms the test suite is comprehensive and CI is green.

---

## Phase 12 — Deployment + CI/CD + release

### Entry criteria
- Phase 11 approved.

### Deliverables
- Multi-stage `Dockerfile` (runtime + web + hermes).
- Production `docker-compose.yml` with health checks, resource limits, restart policies.
- `docker-compose.dev.yml` override for development (hot reload, debug ports).
- GitHub Actions:
  - `ci.yml` — lint, type-check, test, security scan on every PR.
  - `release.yml` — semantic versioning, auto-changelog, Docker image build and push to GHCR, GitHub Release with notes.
  - `codeql.yml` — CodeQL analysis.
  - `dependabot.yml` — dependency updates.
- Branch protection rules enforced.
- `docs/installation.md`, `docs/deployment.md`, `docs/developer-guide.md`, `docs/plugin-sdk.md`, `docs/agent-sdk.md`.
- Architecture diagrams exported as PNG (in addition to Mermaid source) for the README.
- `aaios doctor` command implemented.
- v1.0.0 release published.

### Exit criteria
- A new user can follow `docs/installation.md` and have a running system in under 30 minutes.
- The CI/CD pipeline produces a signed, scanned, v1.0.0 release artifact.
- The repo is public on `github.com/rachidSabah/aaios` with the v1.0.0 release.

### Approval gate
User confirms v1.0.0 is ready for public release.

---

## Cross-phase invariants

The following are enforced continuously from Phase 2 onward, not just at the end:

- **No placeholder code.** Every function does what its docstring says. No `pass`, no `TODO`, no `raise NotImplementedError` in merged code.
- **No untyped code.** `mypy --strict` passes on every commit.
- **No untested code.** Every public function has at least one test. Coverage ≥85%.
- **No insecure code.** `gitleaks`, `bandit`, `pip-audit`, `npm audit` all clean.
- **No undocumented code.** Every public function has a docstring. Every module has a module-level docstring.
- **No bypass of the security layer.** Static-analysis rule (ruff custom) prevents direct use of `subprocess`, `open`, `httpx`, `socket` outside `core/gateway/`.

## How to request changes

At any approval gate, the user can:

1. **Approve** — proceed to the next phase.
2. **Request changes** — describe what needs to change. I will revise the current phase before proceeding.
3. **Request a refactor** — if a better architecture has emerged, describe it. I will document the proposed change, refactor, and resume.
4. **Pause** — the work can be paused and resumed later. The worklog (`worklog.md`) tracks state.

---

This concludes the roadmap. Phase 1 is now ready for review.
