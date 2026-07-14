# Changelog

All notable changes to AAiOS will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html)
once v1.0.0 is released. Until then, the API and on-disk formats may change
without notice between `0.1.x` releases.

## [1.0.0] — 2026-07-14

### Added — Full v1.0.0 release

The complete Agentic AI Operating System — a Windows-first, modular runtime
for orchestrating generic AI agents. 14 phases, 597 tests, 199 source files.

#### Core Architecture (Phases 1-3)
- 5-layer kernel: Event Bus (typed async pub/sub with persistence), State Manager
  (event-sourced with snapshots), Config Manager (5-layer loader with hot-reload),
  Logging (structlog JSON), Telemetry (OpenTelemetry), DI Container, Tool Registry,
  Prompt Registry, Gateway (the only I/O surface — INV-02)
- 10 architecture documents (docs/architecture/)
- 12 design invariants (INV-01 through INV-12), enforced in CI

#### Generic Agent Runtime (Phase 4)
- GenericAgent Protocol (11 methods, runtime_checkable)
- 16 agent type Protocols (Supervisor, Planner, Coding, Desktop, Research, Browser,
  Memory, Reflection, QA, Security, Deployment, Vision, Voice, Document, Workflow, Custom)
- 3 implementation styles (InProcess, SubprocessBridge, RemoteService)
- Agent Registry (capability-based discovery, hot-reload, health monitoring, versioning,
  dependency resolution with cycle detection)
- MockAgent for testing

#### Task Orchestrator (Phase 5)
- Priority queue (5 levels + aging to prevent starvation)
- DAG execution with parallelism (asyncio.gather with semaphore)
- Retry policies (constant/linear/exponential backoff)
- Checkpointing (analog of INV-04 for the Orchestrator)
- Cancellation (cooperative + cascade)
- Scheduler (ONE_TIME, CRON, INTERVAL with max_runs + until)
- Background worker pool (ThreadPool + ProcessPool)
- Human approval gates (pre_step/post_step/pre_commit with timeout)
- Workflow Engine (saved reusable workflows with variable substitution)

#### Model Router (Phase 6)
- 13 LLM providers (OpenAI, Anthropic, Google, OpenRouter, DeepSeek, GLM, NVIDIA,
  Ollama, LM Studio, Azure OpenAI, Mistral, Groq, Custom)
- Automatic failover (retryable errors → next provider)
- Cost tracking (per-task, per-user, per-provider)
- Rate limiting (per-provider token bucket)
- Streaming (SSE multiplexer)
- Tool calling (JSON Schema)
- Health monitoring (auto-degrade at 2 failures, auto-disable at 5)
- Context caching (Anthropic prompt caching)

#### Memory Subsystem (Phase 7)
- 5 memory scopes (short_term, long_term, semantic, conversation, project)
- Vector store (cosine similarity, metadata filtering)
- Knowledge graph (NetworkX-backed, BFS traversal)
- Embeddings (hash-based for tests, sentence-transformers for production)
- RAG pipeline (hybrid vector + graph + keyword + rerank + context window budgeting)
- Compression/summarization (extractive, background scheduler)
- Context windows (per-task bounded, LRU+relevance eviction)
- Memory ranking (weighted: vector 40% + graph 20% + keyword 20% + recency 10% + user_pref 5%)

#### Supervisor + Security (Phase 8)
- DefaultSupervisor (the main loop: goal → plan → dispatch → reflect → correct → QA → commit)
- LlmPlanner (decomposes goals into DAG plans via Model Router)
- CapabilitySelector (scores agents: track_record 40%, load 20%, cost 20%, latency 15%, user_pref 5%)
- DefaultReflectionAgent (ACCEPT/REJECT/NEEDS_CORRECTION)
- DefaultSelfCorrectionAgent (max 3 attempts)
- DefaultQAAgent (PASS/FAIL)
- Security Layer: RBAC (owner/admin/operator/viewer) + ABAC, EncryptedSecretStore
  (Fernet AES-128-CBC + HMAC-SHA256, rotation with grace period), hash-chained audit log
  (SHA-256, tamper detection), SecurityManager (implements Gateway protocols)

#### Agent Implementations (Phases 9-10)
- ClaudeCodeCodingAgent: subprocess bridge to coding CLI, JSON-RPC protocol,
  9 capabilities (code.read/write/refactor/review, test.run, git.commit/push/branch,
  shell.execute), project-scoped filesystem sandbox, mock mode for testing
- HermesDesktopAgent: subprocess bridge to desktop daemon, 14 capabilities
  (9 desktop: ui.click, ui.find_element, input.type_text, input.key_press,
  screen.screenshot, screen.ocr, app.open, app.close, file.manage +
  5 browser: navigate, click, input, extract, screenshot), mock mode

#### Plugins + MCP (Phase 11)
- PluginManager (discovery, install, enable/disable, hot-reload, uninstall)
- MCPManager (discover, register, connect/disconnect, reload, call_tool)
- Plugin SDK (PluginManifestBuilder fluent API, ToolPlugin, AgentPlugin base classes)
- Agent SDK (scaffold_agent generates complete plugin directory with 3 templates)
- 3 example plugins (weather, calculator with safe AST evaluation, openhands scaffold)

#### Dashboard + CLI + API (Phase 12)
- FastAPI server with 30 routes (REST + WebSocket)
- Typer CLI with 12 commands (version, doctor, run, tasks, agents, capabilities,
  providers, models, costs, memory_recall, memory_remember, audit)
- Next.js 16 dashboard (live agents, providers, health, quick links, dark mode)

#### Testing (Phase 13)
- 597 tests across 5 categories: unit (545), integration (14), e2e (8),
  stress (8), performance (5), security (21)
- All tests pass with no network access (all offline, all HTTP/subprocess mocked)
- Architecture invariants (INV-02, INV-09) enforced by tests

#### Deployment (Phase 14)
- Windows installer scaffolding (Inno Setup)
- Docker Compose deployment (nginx + web + api + runtime + worker + postgres + qdrant + redis + otel)
- GitHub Actions CI (Windows + Linux matrix, ruff, mypy, bandit, pytest, pip-audit)
- GitHub Actions release (semantic-release, auto-changelog, Docker push, GitHub Release)
- Documentation: installation, deployment, developer guide, architecture (10 docs)

### Security
- Zero-trust architecture (all I/O through Gateway)
- RBAC + ABAC policy engine (fail-closed DENY by default)
- Encrypted secrets at rest (Fernet, PBKDF2 600k iterations)
- Hash-chained audit log (tamper-evident)
- Secret rotation with grace period
- INV-02: no I/O imports outside gateway/model_router (CI-enforced)
- INV-09: no agent names in core (CI-enforced)

## [Unreleased]

### Added — Phase 2 (repository structure)

- **Monorepo layout** under `core/`, `services/`, `agents/` (with `_types/`,
  `_impls/`, `_base/` subpackages), `supervisor/`, `orchestrator/`,
  `surfaces/` (`api/`, `cli/`, `web/`, `desktop/`), `plugins/`, `tests/`,
  `deploy/{windows,docker}/`, `scripts/`, `docs/{architecture,operations,
  developer,plugin-sdk,agent-sdk}/`.
- **`pyproject.toml`** with Hatchling backend, full ruff config (lint +
  format + isort + bandit + mccabe), mypy `--strict` config, pytest config
  with offline/windows/linux markers, coverage config, pip-audit config.
- **`package.json`** + pnpm workspace, `surfaces/web/package.json` with
  Next.js 16, React 19, Tailwind 4, shadcn/ui dependencies, Vitest, Playwright.
- **`surfaces/web/`** Next.js skeleton: `app/layout.tsx`, `app/page.tsx`
  (health-check page), `lib/api.ts` (API client stub), `globals.css`
  (Tailwind 4 with dark mode), `tsconfig.json`, `next.config.ts`,
  `postcss.config.mjs`, `vitest.config.ts`, `.eslintrc.json`, `.gitignore`.
- **`surfaces/cli/`** Typer-based CLI stub with `aaios version`,
  `aaios doctor`, `aaios dev` commands.
- **`surfaces/api/`** FastAPI stub with `/healthz` and `/readyz` endpoints.
- **`CONTRIBUTING.md`**, **`CODE_OF_CONDUCT.md`** (Contributor Covenant 2.0),
  **`SECURITY.md`** (vulnerability disclosure policy), **`CHANGELOG.md`**.
- **GitHub scaffolding**: `CODEOWNERS`, issue templates (bug, feature,
  plugin-idea, agent-idea), PR template, branch protection documentation.
- **CI workflows** (`.github/workflows/ci.yml`) with a **Windows + Linux
  matrix** running ruff, mypy, bandit, pytest, pip-audit, pnpm build, vitest.
- **Release workflow** (`.github/workflows/release.yml`) using
  semantic-release + auto-changelog + Docker build (optional path).
- **CodeQL workflow** + **Dependabot config**.
- **`tasks.ps1`** (Windows) and **`tasks.sh`** (Linux) task runners with
  `dev`, `test`, `lint`, `typecheck`, `build`, `check`, `clean`,
  `install-windows` commands. **`Makefile`** wrapper for convenience.
- **`Dockerfile`** (multi-stage, runtime + web) + **`docker-compose.yml`**
  + **`.dockerignore`** — the optional Docker deployment path.
- **Windows installer scaffolding** (`deploy/windows/aaios.iss` Inno Setup
  script + `deploy/windows/bootstrap.ps1` PowerShell bootstrap).
- **`config/`** directory with `mcp-servers/` and `agents/` subdirectories
  for runtime configuration.
- **`docs/`** subdirectories reserved for Phase 12+ deliverables:
  `operations/`, `developer/`, `plugin-sdk/`, `agent-sdk/`.

### Changed

- Renamed architecture docs `02-08` → `03-09` to make room for the new
  `02-generic-agent-runtime.md` (Phase 1 refactor).
- README updated to reflect Generic Agent Runtime framing and Windows-first
  principle.

### Security

- Threat model, RBAC + ABAC, secret store with rotation, Windows sandboxing
  (Job Objects + AppContainer + WDAC), hash-chained audit log, permission
  approval flow — all specified in
  [`docs/architecture/07-security-model.md`](docs/architecture/07-security-model.md).
  Implementation lands in Phase 3 (`core/gateway/`, `services/security/`).

## [0.1.0.dev0] — 2026-07-14

### Added — Phase 1 (architecture)

- **Apache 2.0 LICENSE**, `.gitignore`, initial `README.md`.
- **10 architecture documents** in `docs/architecture/`:
  - `00-overview.md` — executive overview, 5-layer model, document map
  - `01-goals-and-principles.md` — 6 goals, 6 principles (ordered), 12
    invariants (INV-01 through INV-12), explicit trade-offs, deferred
    decisions, 10 success criteria
  - `02-generic-agent-runtime.md` — **the centerpiece.** `GenericAgent`
    interface (11 methods), 16 agent types, capability manifests,
    capability-based selection, implementation-agnostic contracts
  - `03-system-design.md` — kernel, Task Orchestrator (queue/DAG/checkpoint/
    resume/scheduling/approval gates), supervisor-as-agent loop, e2e flow
  - `04-component-map.md` — every named component with responsibility/owns/
    depends on/exposes/failure modes
  - `05-data-flow.md` — 4 end-to-end scenarios (coding, desktop, RAG, plugin
    install), all written against agent types not product names
  - `06-tech-stack.md` — locked stack (Windows-first), rationale, rejected
    alternatives
  - `07-security-model.md` — zero-trust, RBAC+ABAC, Windows sandboxing,
    secrets with rotation, audit, permission flow, least-privilege
  - `08-deployment-topology.md` — Windows-native primary, Docker optional,
    Linux compat path
  - `09-roadmap.md` — 14-phase build plan with entry/exit criteria per phase

### Architecture decisions

- **Generic Agent Runtime** — the Supervisor orchestrates capabilities, not
  products. Claude Code and Hermes are first-class *examples* of agent
  implementations, not architectural dependencies.
- **Windows-first** — native Windows Services + Task Scheduler + PowerShell;
  Docker is optional. Linux support is a v1.1 goal via an abstraction layer.
- **Task Orchestrator** as an L4 peer of the Supervisor — owns queue, DAG,
  checkpoint, resume, scheduling, approval gates.
- **Centralized Model Router** — agents never call LLM providers directly.
- **Event-sourced state** with snapshotting for fast replay.
- **Gateway** as the only I/O surface — INV-02 enforced in CI.
