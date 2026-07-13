# Changelog

All notable changes to AAiOS will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html)
once v1.0.0 is released. Until then, the API and on-disk formats may change
without notice between `0.1.x` releases.

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
