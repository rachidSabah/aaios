# Contributing to AAiOS

First off, thank you for considering a contribution to AAiOS. This document describes how to contribute effectively.

> **Pre-alpha status:** AAiOS is currently in Phase 2 (repository structure). The architecture is approved; the implementation is being built phase-by-phase. Until v1.0.0, only contributions aligned with the active phase in [`docs/architecture/09-roadmap.md`](docs/architecture/09-roadmap.md) will be accepted.

## 1. Read the architecture first

Before writing any code, read at least:

- [`docs/architecture/00-overview.md`](docs/architecture/00-overview.md) — what AAiOS is.
- [`docs/architecture/02-generic-agent-runtime.md`](docs/architecture/02-generic-agent-runtime.md) — the `GenericAgent` interface and the 16 agent types. **The most important doc.**
- [`docs/architecture/06-tech-stack.md`](docs/architecture/06-tech-stack.md) — the locked technology choices.
- [`docs/architecture/07-security-model.md`](docs/architecture/07-security-model.md) — the zero-trust security model.

Every PR is reviewed against the design invariants in [`docs/architecture/01-goals-and-principles.md`](docs/architecture/01-goals-and-principles.md) (INV-01 through INV-12). Violations block merge.

## 2. Development environment

### 2.1 Prerequisites

- **Windows 11** (primary) or **Linux** (v1.1, secondary)
- **Python 3.12+** — [python.org](https://www.python.org/downloads/) (Windows) or your distro's package manager (Linux)
- **Node.js 22 LTS** — [nodejs.org](https://nodejs.org/)
- **pnpm 9+** — `npm install -g pnpm`
- **Git 2.40+**
- **PostgreSQL 16** (optional — SQLite works for dev/test)
- **Qdrant 1.10+** (optional — only needed for memory subsystem work in Phase 7+)

### 2.2 Setup

```powershell
# Clone your fork
git clone https://github.com/<your-username>/aaios.git
cd aaios

# Create a Python virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1   # Windows
# source .venv/bin/activate    # Linux/macOS

# Install Python deps (including dev extras)
pip install -e ".[dev,windows]"   # Windows
# pip install -e ".[dev,linux]"   # Linux

# Install Node deps
pnpm install

# Verify
aaios version
aaios doctor
```

### 2.3 Daily workflow

```powershell
# Run all checks before pushing
tasks lint           # ruff + mypy + bandit
tasks test           # pytest + vitest
tasks typecheck      # tsc --noEmit for the web

# Or run them all at once:
tasks check
```

See [`tasks.ps1`](tasks.ps1) (Windows) or [`tasks.sh`](tasks.sh) (Linux) for the full list of commands.

## 3. Code standards

### 3.1 Python
- **Typed everywhere.** `mypy --strict` must pass. No `Any`, no `# type: ignore` without a justification comment.
- **Pydantic v2** for all data models crossing module boundaries. No bare `dict`.
- **Async first.** No blocking I/O in async functions. Use `httpx.AsyncClient`, `asyncio.to_thread`, etc.
- **Google-style docstrings** on every public function, class, and module.
- **No placeholder code.** No `pass`, no `TODO` without an issue link, no `raise NotImplementedError` (except in explicitly-stubbed Linux adapters, which must be labeled).

### 3.2 TypeScript / React
- **Strict mode.** `tsconfig.json` has `"strict": true`.
- **Function components** with hooks. No class components.
- **Server Components by default**; `"use client"` only when interactivity is required.
- **TanStack Query** for server state; **Zustand** for client state.
- **shadcn/ui** for primitives; **Tailwind 4** for styling.

### 3.3 Architecture invariants (enforced in CI)

| ID | Rule |
|----|------|
| INV-01 | Layer dependencies flow inward only (L5 → L1). |
| INV-02 | No `subprocess`, `open`, `httpx`, `socket` outside `core/gateway/`. |
| INV-03 | Pydantic models only — no bare dicts across modules. |
| INV-04 | Events persisted before side effects. |
| INV-05 | No secrets in code/configs/logs. |
| INV-09 | No agent implementation names (`claude`, `hermes`, `openhands`, `cline`, `roo`, `gemini`, `codex`) in `core/`, `services/`, `supervisor/`, `orchestrator/`, `surfaces/`. |
| INV-10 | Every `GenericAgent` implementation satisfies the 11-method interface. |

A custom ruff plugin (Phase 3) and a mypy plugin enforce these automatically.

## 4. Commit conventions

We use [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <subject>

<body>

<footer>
```

Types: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`, `build`, `ci`, `perf`.

Scopes (align with the monorepo layout): `core`, `services`, `agents`, `supervisor`, `orchestrator`, `surfaces`, `plugins`, `docs`, `deploy`, `ci`.

Example:

```
feat(agents): add ClaudeCodeCodingAgent subprocess bridge

Implements the GenericAgent interface for Claude Code via the official
`claude` CLI. Includes JSON-RPC protocol, capability manifest, and a
project-scoped filesystem sandbox.

Closes #42
```

## 5. Pull request process

1. **Open an issue first** for any non-trivial change (more than ~50 lines). Discuss the approach before writing code.
2. **Branch from `main`**: `feat/<short-description>`, `fix/<short-description>`, etc.
3. **One concern per PR.** A PR that mixes a refactor and a feature will be rejected.
4. **All CI checks must pass** on both `windows-latest` and `ubuntu-latest`.
5. **Coverage must not drop** below 85% on the files you touched.
6. **Update `CHANGELOG.md`** under the `Unreleased` section.
7. **At least one review** from a CODEOWNER. New contributors: be patient, we'll review thoughtfully.
8. **Squash-and-merge** to `main`. The PR title becomes the commit message.

## 6. Adding a new agent (the most common contribution post-v1)

Follow the [Agent SDK guide](docs/agent-sdk/README.md) (lands in Phase 11). Summary:

1. Implement the `GenericAgent` interface (or a type-specific sub-protocol like `CodingAgent`).
2. Define a `CapabilityManifest`.
3. Register via a Python entry point in your plugin's `pyproject.toml`.
4. Write tests using the mock supervisor.
5. Submit as a plugin package to the marketplace (separate repo) — or, for built-in agents, as a PR to `agents/_impls/`.

**Critical:** your agent must not be referenced by name anywhere outside its own package. The Supervisor discovers it via the Agent Registry, never by name.

## 7. Reporting bugs

Use the **Bug report** GitHub issue template. Include:

- AAiOS version (`aaios version`)
- OS and version
- Python version
- Steps to reproduce
- Expected vs actual behavior
- Logs (sanitize secrets first — see [`SECURITY.md`](SECURITY.md))
- `aaios doctor` output

## 8. Reporting security vulnerabilities

**Do NOT open a public issue.** See [`SECURITY.md`](SECURITY.md) for the private disclosure process.

## 9. Code of conduct

Participation in this project is governed by the [Code of Conduct](CODE_OF_CONDUCT.md). Be excellent to each other.

## 10. License

By contributing, you agree that your contributions will be licensed under the [Apache 2.0 License](LICENSE).
