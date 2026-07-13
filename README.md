# Agentic AI Operating System (AAiOS)

> A modular, production-grade operating system for autonomous AI agents — orchestrating multiple LLM providers, agent runtimes (Claude Code, Hermes), MCP servers, vector memory, knowledge graphs, plugins, and workflows behind a single supervisor.

[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)
[![Status: Phase 1 — Architecture](https://img.shields.io/badge/Phase-1%20Architecture-orange)](docs/architecture/08-roadmap.md)
[![Python 3.12+](https://img.shields.io/badge/Python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![Next.js 16](https://img.shields.io/badge/Next.js-16-black.svg)](https://nextjs.org/)

---

## What this is

AAiOS is an **enterprise-grade, open-source Agentic AI Operating System**. It is not a chatbot wrapper. It is a fully modular runtime that lets you compose multiple AI models, multiple specialized agents, persistent memory, external tool servers (MCP), and user-defined workflows into a single autonomous system — supervised by a reflection-driven planner that can correct its own mistakes.

The system is designed to rival closed-source enterprise AI assistants (Devin, Cursor Agent, OpenAI Operator, Anthropic Claude for Enterprise) while remaining modular, self-hostable, and extensible by anyone.

## Architecture at a glance

```
                ┌──────────────────────────────────────────────────┐
                │                  USER LAYER                      │
                │   CLI   •   Web UI   •   Desktop App   •   API   │
                └───────────────────────┬──────────────────────────┘
                                        │
                ┌───────────────────────▼──────────────────────────┐
                │              SUPERVISOR AGENT                    │
                │  Executive Planner • Agent Router • Reflection   │
                │  Self-Correction • QA • Workflow Engine          │
                └─────┬──────────┬──────────┬──────────┬──────────┘
                      │          │          │          │
              ┌───────▼──┐ ┌─────▼────┐ ┌───▼────┐ ┌───▼────────┐
              │  Model   │ │  Agent   │ │ Memory │ │  Plugin    │
              │  Router  │ │  Roster  │ │ Manager│ │  / MCP     │
              └────┬─────┘ └────┬─────┘ └───┬────┘ └─────┬──────┘
                   │            │           │            │
        ┌──────────▼┐    ┌──────▼──────┐ ┌──▼──────┐ ┌───▼─────────┐
        │ Providers │    │ Claude Code │ │ Qdrant  │ │ MCP Servers │
        │ OpenRouter│    │ Hermes      │ │ Postgres│ │ Plugins     │
        │ Anthropic │    │ Research    │ │ KG      │ │ Tools       │
        │ OpenAI …  │    │ Browser …   │ │ Embed.  │ │             │
        └───────────┘    └─────────────┘ └─────────┘ └─────────────┘
```

Full architecture documents: **[`docs/architecture/`](docs/architecture/)**

## Core capabilities

- **Supervisor-driven autonomy** — an Executive Planner decomposes goals, an Agent Router dispatches to the right specialist, a Reflection Agent critiques, and a Self-Correction Agent repairs before output.
- **Poly-model routing** — OpenRouter, OpenAI, Anthropic, Google, Mistral, DeepSeek, GLM, NVIDIA, Ollama, LM Studio, and custom APIs — with automatic failover, cost tracking, rate limiting, streaming, tool calling, vision, reasoning, and context caching.
- **Agent roster** — Claude Code (engineering), Hermes (desktop automation), plus Research, Browser, Memory, QA, Reflection, and Planner agents.
- **Multi-layer memory** — short-term, long-term, semantic, conversation, and project memory, backed by Qdrant vector storage, a knowledge graph, embeddings, compression, summarization, and RAG retrieval.
- **MCP-compliant** — discover, register, authenticate, monitor, hot-reload any Model Context Protocol server.
- **Plugin SDK** — add agents, tools, providers, dashboards, workflows, memory adapters, and automation without rebuilding the runtime.
- **Zero-trust security** — OAuth, API keys, encrypted secrets, RBAC, sandboxing, permission approvals, audit logs, and encrypted storage.
- **Operator-grade UX** — modern Next.js dashboard with workflow builder, prompt library, agent monitor, live logs, task queue, memory explorer, plugin marketplace, and per-provider analytics — in dark and light mode.

## Repository status

This repository is being built phase-by-phase. The current state is:

| Phase | Status | Description |
|-------|--------|-------------|
| 1 | ✅ **In review** | Architecture design, diagrams, security model, deployment topology |
| 2 | ⏳ Pending approval | Repository structure, GitHub scaffolding, CI skeleton |
| 3 | ⏳ Pending | Core framework (event bus, state, config, logging, registries) |
| 4 | ⏳ Pending | Supervisor + planning agents |
| 5 | ⏳ Pending | Memory subsystem |
| 6 | ⏳ Pending | Model Router |
| 7 | ⏳ Pending | Claude Code integration |
| 8 | ⏳ Pending | Hermes integration |
| 9 | ⏳ Pending | Plugins + MCP |
| 10 | ⏳ Pending | Dashboard + CLI + API |
| 11 | ⏳ Pending | Testing matrix |
| 12 | ⏳ Pending | Deployment + CI/CD + first release |

See [`docs/architecture/08-roadmap.md`](docs/architecture/08-roadmap.md) for the full plan.

## Tech stack

| Layer | Technology |
|-------|-----------|
| Backend runtime | Python 3.12, asyncio, Pydantic v2, SQLAlchemy 2 (async) |
| Frontend | Next.js 16, React 19, Tailwind 4, shadcn/ui |
| Relational DB | PostgreSQL 16 (prod) + SQLite (dev/test) |
| Vector DB | Qdrant |
| Knowledge graph | In-process graph layer (NetworkX-backed) with optional Neo4j adapter |
| Message bus | In-process async event bus + optional Redis pub/sub adapter |
| Agent bridges | Subprocess + JSON-RPC over stdin/stdout (Claude Code, Hermes daemon) |
| Containerization | Docker + Docker Compose |
| License | Apache 2.0 |

## License

Apache License 2.0 — see [`LICENSE`](LICENSE).

## Contributing

Contribution guide, code of conduct, issue/PR templates, and SDK documentation land in **Phase 2**. Until then, this repository is in pre-alpha architecture review — no PRs will be accepted.
