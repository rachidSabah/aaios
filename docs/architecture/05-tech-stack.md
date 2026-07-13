# 05 — Technology Stack

> **Audience:** all stakeholders.
> **Purpose:** record the locked technology choices, the rationale, and the rejected alternatives. This document is the single source of truth for "what is AAiOS built on."

---

## 1. Locked stack

| Layer | Component | Technology | Version |
|-------|-----------|-----------|---------|
| **Backend runtime** | Language | Python | 3.12+ |
| | Async runtime | asyncio + uvloop | stdlib + 0.19+ |
| | HTTP framework | FastAPI | 0.115+ |
| | ASGI server | Uvicorn (workers=1, async loop) | 0.32+ |
| | Validation | Pydantic | v2 |
| | ORM | SQLAlchemy | 2.x (async) |
| | Migrations | Alembic | 1.13+ |
| | CLI | Typer + Rich | 0.12+ / 13.7+ |
| | DI | dependency-injector (or in-house) | 4.41+ |
| | Templating | Jinja2 | 3.1+ |
| | Testing | pytest + pytest-asyncio + hypothesis | 8.x / 0.23+ / 6.x |
| | Static analysis | ruff + mypy + bandit | 0.6+ / 1.11+ / 1.7+ |
| | Secret scanning | gitleaks | 8.18+ |
| **Frontend** | Framework | Next.js | 16 (App Router, RSC) |
| | UI library | React | 19 |
| | Styling | Tailwind CSS | 4 |
| | Component system | shadcn/ui | latest |
| | State | Zustand + TanStack Query | 4.x / 5.x |
| | Forms | react-hook-form + zod | 7.x / 3.x |
| | Charts | Recharts | 2.x |
| | WebSockets | native + socket.io-client | — |
| | Testing | Vitest + Playwright | 1.6+ / 1.45+ |
| **Data layer** | Relational DB (prod) | PostgreSQL | 16 |
| | Relational DB (dev/test) | SQLite | 3.45+ |
| | Vector DB | Qdrant | 1.10+ |
| | Knowledge graph (default) | NetworkX (in-process) | 3.3+ |
| | Knowledge graph (optional) | Neo4j | 5.x |
| | Cache / pub-sub | Redis | 7.x |
| | Embeddings | OpenAI / local sentence-transformers | — |
| **Agent runtimes** | Claude Code | official `claude` CLI | latest |
| | Hermes | in-house daemon (Python + PyAutoGUI + Playwright) | 0.1 |
| **Containerization** | Container | Docker | 24+ |
| | Orchestration | Docker Compose | 2.20+ |
| | Images | python:3.12-slim, node:22-alpine, postgres:16, redis:7, qdrant/qdrant | — |
| **CI/CD** | GitHub Actions | hosted runners | — |
| | Release | semantic-release + auto-changelog | — |
| **Observability** | Telemetry | OpenTelemetry SDK + OTLP exporter | 1.25+ |
| | Logs | structlog → JSON | 24.x |
| **Security** | Auth | OAuth2 (Authlib) + API keys | — |
| | Authorization | Cedar-style policy engine or `opea` | — |
| | Secret encryption | `cryptography.fernet` (AES-128-CBC + HMAC) | — |
| | Sandboxing | restricted Python `__builtins__` + seccomp (Linux) | — |

## 2. Rationale per layer

### 2.1 Backend — Python 3.12
**Choice:** Python 3.12.
**Why:** The LLM ecosystem is Python-first. The MCP SDK, OpenAI SDK, Anthropic SDK, Google SDK, Mistral SDK, sentence-transformers, langchain, llama_index — all Python. Any other language would require us to either re-implement these SDKs (huge effort, perpetually behind) or shell out to Python anyway (which defeats the purpose). Python 3.12 specifically brings better error messages, faster startup, and `match` statement maturity.
**Rejected:**
- *TypeScript/Node* — stronger type system and unified stack with frontend, but we would have to wrap every Python SDK or rewrite it. The MCP SDK in TS is also less mature than the Python one.
- *Go* — excellent concurrency and single-binary deployment, but the AI ecosystem is essentially nonexistent. We would end up with a Go supervisor calling Python subprocesses for every model call.
- *Rust* — best performance and memory safety, but dev velocity is too low for the scope of this project, and the AI ecosystem is the smallest of the four.

### 2.2 Frontend — Next.js 16 + React 19
**Choice:** Next.js 16 (App Router, RSC) with React 19.
**Why:** App Router + React Server Components give us a clean split between data-heavy dashboard pages (server-rendered, fast first paint) and interactive widgets (client components, hydrated). shadcn/ui gives us accessible, themeable components without locking us into a component library — we own the code. Tailwind 4 is the right level of abstraction (utility-first, no CSS-in-JS runtime cost). Next.js 16 specifically brings improved caching, partial prerendering, and Turbopack stability.
**Rejected:**
- *SvelteKit* — lighter runtime and excellent DX, but smaller ecosystem for the kind of complex dashboard widgets (workflow builder, agent monitor, memory explorer) we need to build.
- *Vue 3 + Nuxt* — strong in its own right, but smaller enterprise AI footprint and a smaller pool of contributors familiar with it.
- *Tauri + React* — attractive for the desktop app, but using it for the web UI too would complicate deployment (the web UI should be deployable without a Rust toolchain).

### 2.3 Vector DB — Qdrant
**Choice:** Qdrant 1.10+.
**Why:** Rust core (fast, low memory), excellent filtering (we need metadata filters for memory scoping), native Docker image, generous free tier on Qdrant Cloud for users who want managed, simple Python SDK. Supports both dense and sparse vectors (hybrid search).
**Rejected:**
- *pgvector* — would let us merge relational + vector into Postgres (one fewer service), but its filtering is weaker, its performance at scale is worse than Qdrant, and we want the vector store to be independently scalable.
- *Chroma* — easiest local dev, Python-native, but production maturity at >10M vectors is unproven and the project's velocity has been uneven.
- *Milvus* — best at massive scale (billions of vectors), but the ops surface (multiple components: etcd, MinIO, Pulsar) is overkill for a system that is explicitly single-tenant self-hosted in v1.

### 2.4 Relational DB — PostgreSQL 16 (prod) + SQLite (dev/test)
**Choice:** Postgres 16 for production, SQLite for dev/test, both via SQLAlchemy 2 async.
**Why:** Postgres is the industry default for production workloads — JSONB for flexible event payloads, mature HA, pgvector as a fallback if Qdrant is unavailable. SQLite for dev/test means a contributor can clone the repo and run the full test suite with zero external services. SQLAlchemy 2's async API and Core/ORM split let us support both transparently. The event-sourced state manager uses a JSONB column for event payloads on Postgres and a TEXT column on SQLite — the SQLAlchemy layer hides this.
**Rejected:**
- *Postgres-only* — would force every contributor to run Postgres locally, raising the barrier to entry.
- *SQLite-only* — great for single-user desktop but cannot handle the concurrency of a real multi-agent deployment.
- *MongoDB* — flexible schema is tempting for event sourcing, but we lose transactional guarantees and SQL tooling, and the user base is more familiar with SQL.

### 2.5 Agent binding — subprocess + JSON-RPC
**Choice:** Claude Code and Hermes run as subprocesses; the supervisor communicates with them over JSON-RPC on stdin/stdout.
**Why:** Process isolation (a Hermes crash cannot take down the supervisor), language independence (Claude Code stays as the official Python/TS CLI, Hermes can later be rewritten in Rust without changing the supervisor), independent versioning (each agent can be upgraded without restarting the supervisor). The latency cost (~5 ms per call) is negligible compared to LLM latency (seconds).
**Rejected:**
- *HTTP/gRPC microservices* — more flexible but more infrastructure (service discovery, health checks, TLS between services). Overkill for a single-machine deployment.
- *In-process Python plugins* — fastest, but loses isolation. A segfault in Hermes would take down the supervisor. We keep this option for purely computational agents (Reflection, QA) where the LLM call is the bottleneck anyway.

### 2.6 License — Apache 2.0
**Choice:** Apache 2.0.
**Why:** Maximum enterprise adoption (enterprises will not deploy AGPL software), explicit patent grant (matters for a system that integrates many third-party APIs), compatible with virtually all other open-source licenses (so we can reuse libraries freely). The system's value is in the orchestration layer, not in any individual component — copyleft would not protect us meaningfully and would hurt adoption.
**Rejected:**
- *MIT* — simpler, but no explicit patent grant. For a system this complex with this many third-party integrations, the patent grant matters.
- *AGPL-3.0* — protects against cloud re-hosting, but kills enterprise adoption. We would rather have enterprises self-host AAiOS than have them not use it at all.
- *BSL / Elastic License* — source-available, converts to open after 4 years. Used by Sentry/Redis. Attractive for a commercial project, but we are explicitly open-source.

### 2.7 Deployment — Docker Compose
**Choice:** Docker Compose for v1, with a documented path to Kubernetes in v1.1.
**Why:** Single `docker compose up` is the right deployment story for self-hosted single-tenant. Compose files are declarative, version-controlled, and easy to reason about. Kubernetes is overkill for v1 (we are not multi-tenant, not multi-region, not autoscaling). The Compose file is structured so that the path to Helm is mechanical — every service in the Compose file maps to a Deployment + Service in Helm.
**Rejected:**
- *Kubernetes-only* — heaviest ops surface, blocks individual users from self-hosting.
- *Compose + Helm from day one* — doubles the DevOps surface in Phase 12 for no user benefit in v1.

## 3. Compatibility and versioning

- **Python:** 3.12 minimum. 3.13 supported when it stabilizes (October 2024 release). We will not require 3.13 features until 3.14 is out.
- **Node:** 22 LTS. Next.js 16 requires Node 18.18+, but we standardize on 22 LTS for the longest support window.
- **Postgres:** 16 minimum. We use `JSONB` and `GENERATED ALWAYS AS` columns, both 12+. 16 is the current LTS.
- **Qdrant:** 1.10+ (for sparse vector support).
- **Docker:** Compose v2 (the `docker compose` plugin, not the legacy `docker-compose` binary).

## 4. Dependency policy

- All third-party Python dependencies must be pinned in `pyproject.toml` with `~=` (compatible release) and have a corresponding hash in `requirements.lock`.
- All npm dependencies must be pinned in `package.json` with `^` (caret) and locked in `pnpm-lock.yaml`.
- Renovate bot opens PRs for outdated deps. Major bumps require a manual review and a CI run on a matrix of the old + new version.
- Any dependency that has not seen a release in 24 months is flagged for replacement.
- Any dependency with an unpatched Critical CVE is auto-replaced within 7 days.

## 5. Build artifacts

| Artifact | Where | Produced by |
|----------|-------|-------------|
| Python wheel | `dist/aaios-*.whl` | `hatch build` |
| Docker images | `ghcr.io/rachidSabah/aaios-{runtime,web,hermes,worker}` | GitHub Actions |
| CLI binary | `dist/aaios` (PyInstaller) | GitHub Actions (release only) |
| Documentation site | `https://aaios.dev` (deferred) | MkDocs Material |

This concludes the tech stack document. For the security implications of these choices, see [`06-security-model.md`](06-security-model.md).
