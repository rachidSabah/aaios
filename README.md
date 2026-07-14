# Agentic AI Operating System (AAiOS)

> A **Windows-first**, modular, production-grade operating system for autonomous AI agents — orchestrating multiple LLM providers, multiple **generic** agents, MCP servers, vector memory, knowledge graphs, plugins, and workflows behind a single supervisor. Built around a **Generic Agent Runtime** where Claude Code, Hermes, and any future agent (OpenHands, Cline, Roo Code, Gemini CLI, Codex CLI, custom) are all just replaceable implementations.

[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)
[![Status: Phase 1 — Architecture (refactored)](https://img.shields.io/badge/Phase-1%20Architecture%20(refactored)-orange)](docs/architecture/09-roadmap.md)
[![Python 3.12+](https://img.shields.io/badge/Python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![Next.js 16](https://img.shields.io/badge/Next.js-16-black.svg)](https://nextjs.org/)
[![Windows 11](https://img.shields.io/badge/Platform-Windows%2011%20first-blue.svg)](https://www.microsoft.com/windows/)

---

## What this is

AAiOS is an **enterprise-grade, open-source Agentic AI Operating System**. It is not a chatbot wrapper. It is a fully modular runtime that lets you compose multiple AI models, multiple specialized agents, persistent memory, external tool servers (MCP), and user-defined workflows into a single autonomous system — supervised by a reflection-driven planner that can correct its own mistakes, with every decision observable and replayable.

The system is designed to rival closed-source enterprise AI assistants (Devin, Cursor Agent, OpenAI Operator, Manus AI, OpenHands) while remaining **modular, self-hostable, Windows-native, and extensible by anyone**.

## The core design principle

**The Supervisor orchestrates capabilities, not products.** Every agent — Claude Code, Hermes, OpenHands, Cline, Roo Code, Gemini CLI, Codex CLI, or any future agent — implements the same `GenericAgent` interface (11 methods: `initialize`, `shutdown`, `discover_capabilities`, `execute_task`, `stream_progress`, `cancel_task`, `report_health`, `report_metrics`, `request_permission`, `serialize_state`, `restore_state`) and advertises a `CapabilityManifest`. The Supervisor asks the Agent Registry: *"which agents can handle capability X?"* and chooses based on health, load, cost, and track record. It never asks *"give me Claude Code"*.

This is what makes the system future-proof. When a new coding agent ships, it is added by writing a new `GenericAgent` implementation and registering it. The Supervisor, the Task Orchestrator, the Memory, the Security Layer, the Dashboard — **none of them change.**

## Architecture at a glance

```
                ┌──────────────────────────────────────────────────────┐
                │                  USER LAYER                          │
                │   CLI   •   Web UI   •   Desktop App   •   API       │
                └─────────────────────────┬────────────────────────────┘
                                          │
                ┌─────────────────────────▼────────────────────────────┐
                │              SUPERVISOR AGENT                        │
                │  (one implementation of SupervisorAgent type)        │
                │  Planner • Capability Selector • Reflection          │
                │  Self-Correction • QA                                │
                │                                                      │
                │  TASK ORCHESTRATOR                                   │
                │  Queue • DAG • Checkpoint • Resume • Schedule        │
                │  Approval Gates • Background Workers                 │
                └─────┬──────────┬──────────┬──────────┬───────────────┘
                      │          │          │          │
              ┌───────▼──┐ ┌─────▼────┐ ┌───▼────┐ ┌───▼────────────┐
              │  Model   │ │  Agent   │ │ Memory │ │  Plugin / MCP  │
              │  Router  │ │ Registry │ │ Manager│ │  Manager       │
              └────┬─────┘ └────┬─────┘ └───┬────┘ └─────┬──────────┘
                   │            │           │            │
        ┌──────────▼┐    ┌──────▼──────┐ ┌──▼──────┐ ┌───▼─────────────┐
        │ Providers │    │ GENERIC     │ │ Qdrant  │ │ MCP Servers     │
        │ OpenAI    │    │ AGENT       │ │ Postgres│ │ Plugins         │
        │ Anthropic │    │ RUNTIME     │ │ KG      │ │ Tools           │
        │ Google    │    │             │ │ Embed.  │ │                 │
        │ DeepSeek  │    │ 16 types:   │ │ Context │ │                 │
        │ GLM       │    │ Coding (CC, │ │ Windows │ │                 │
        │ NVIDIA    │    │  OH, Cline, │ │         │ │                 │
        │ Ollama    │    │  Roo, …)    │ │         │ │                 │
        │ LM Studio │    │ Desktop     │ │         │ │                 │
        │ Azure     │    │ (Hermes, …) │ │         │ │                 │
        │ Mistral   │    │ Planner,    │ │         │ │                 │
        │ Groq      │    │ Research,   │ │         │ │                 │
        │ Custom    │    │ Browser,    │ │         │ │                 │
        └───────────┘    │ Memory,     │ └─────────┘ └─────────────────┘
                         │ Reflection, │
                         │ QA,         │
                         │ Security,   │
                         │ Deployment, │
                         │ Vision,     │
                         │ Voice, Doc, │
                         │ Workflow,   │
                         │ Custom      │
                         └─────────────┘
```

Full architecture documents: **[`docs/architecture/`](docs/architecture/)** — start with [`00-overview.md`](docs/architecture/00-overview.md), then [`02-generic-agent-runtime.md`](docs/architecture/02-generic-agent-runtime.md).

## Core capabilities

- **Generic Agent Runtime** — 11-method `GenericAgent` interface, 16 agent types (Supervisor, Planner, Coding, Desktop, Research, Browser, Memory, Reflection, QA, Security, Deployment, Vision, Voice, Document, Workflow, Custom). Add any future agent without touching core.
- **Capability-based selection** — the Supervisor picks agents by what they can do, not by name. Multiple implementations of the same type compete on track record, cost, latency, and load.
- **Task Orchestrator** — priority queue, DAG execution with parallelism, retry policies, checkpointing, crash-resume, cancellation, scheduling (via Windows Task Scheduler), background workers, human approval gates.
- **Poly-model routing** — 13 LLM providers with automatic failover, cost tracking, rate limiting, streaming, tool calling, vision, reasoning, context caching, priority routing, health monitoring, and retries. **Agents never call providers directly — all LLM access goes through the centralized Model Router.**
- **Multi-layer memory** — short-term, long-term, semantic, conversation, project memory, backed by Qdrant vector storage, a knowledge graph, embeddings, compression, summarization, ranking, context-window management, and RAG retrieval.
- **MCP-compliant** — discover, register, authenticate, monitor, hot-reload any Model Context Protocol server.
- **Plugin + Agent SDK** — add agents, tools, providers, dashboards, workflows, memory adapters, and automation without rebuilding the runtime. Scaffolds new agent plugins in one command.
- **Zero-trust security** — OAuth, API keys, encrypted secrets **with rotation**, RBAC + ABAC, Windows-native sandboxing (Job Objects, AppContainer, WDAC), permission approval flow, least-privilege analyzer, hash-chained audit log.
- **Operator-grade UX** — modern Next.js dashboard with workflow builder, prompt library, agent monitor (capability-indexed, not name-indexed), live logs, task queue, memory explorer, plugin marketplace, per-provider analytics, approval-gate queue, least-privilege report, secret rotation UI — in dark and light mode.
- **Windows-first** — native Windows Services (NSSM / pywin32), Task Scheduler integration, PowerShell-first shell, Windows paths, Windows Defender integration, optional Docker for those who want it.

## The 16 agent types

| Type | Capabilities | Built-in implementation | Future implementations |
|------|--------------|------------------------|------------------------|
| SupervisorAgent | `supervise.*` | `DefaultSupervisor` | alternative supervisors |
| PlannerAgent | `plan.*` | `LlmPlanner` | — |
| CodingAgent | `code.*`, `test.run`, `git.*`, `shell.execute` | `ClaudeCodeCodingAgent` (wraps `claude` CLI) | OpenHands, Cline, Roo Code, Gemini CLI, Codex CLI |
| DesktopAgent | `desktop.*`, `browser.*` | `HermesDesktopAgent` | AutoHotkey, pywinauto, OS-native |
| ResearchAgent | `web.*`, `cite.*` | `DefaultResearchAgent` | — |
| BrowserAgent | `browser.*` | `PlaywrightBrowserAgent` | — |
| MemoryAgent | `memory.*` | `DefaultMemoryAgent` | — |
| ReflectionAgent | `reflect.*` | `DefaultReflectionAgent` | — |
| QAAgent | `qa.*` | `DefaultQAAgent` | — |
| SecurityAgent | `security.*` | `BanditSecurityAgent` etc. | — |
| DeploymentAgent | `deploy.*` | `DockerDeploymentAgent` etc. | — |
| VisionAgent | `vision.*` | `DefaultVisionAgent` | — |
| VoiceAgent | `voice.*` | (stub in v1) | post-v1 |
| DocumentAgent | `doc.*` | `PdfDocumentAgent` etc. | — |
| WorkflowAgent | `workflow.*` | `DefaultWorkflowAgent` | — |
| CustomAgent | `custom.*` | (plugin-provided) | (plugin-provided) |

## Repository status

This repository is being built phase-by-phase. The current state is:

| Phase | Status | Description |
|-------|--------|-------------|
| 1 | ✅ **In review (refactored)** | Architecture design — Generic Agent Runtime, 16 agent types, Windows-first, 10 architecture docs |
| 2 | ⏳ Pending approval | Repository structure, GitHub scaffolding, Windows+Linux CI matrix |
| 3 | ⏳ Pending | Core framework (kernel + Gateway + platform adapters) |
| 4 | ⏳ Pending | Generic Agent Runtime + Agent Registry |
| 5 | ⏳ Pending | Task Orchestrator |
| 6 | ⏳ Pending | Model Router (13 providers) |
| 7 | ⏳ Pending | Memory subsystem |
| 8 | ⏳ Pending | Supervisor + Planner + Reflection + QA |
| 9 | ⏳ Pending | First CodingAgent implementation (Claude Code) |
| 10 | ⏳ Pending | First DesktopAgent implementation (Hermes) |
| 11 | ⏳ Pending | Plugins + MCP + Plugin/Agent SDK |
| 12 | ⏳ Pending | Dashboard + CLI + API |
| 13 | ⏳ Pending | Testing matrix |
| 14 | ⏳ Pending | Windows deployment + CI/CD + v1.0.0 release |

See [`docs/architecture/09-roadmap.md`](docs/architecture/09-roadmap.md) for the full plan.

## Tech stack

| Layer | Technology |
|-------|-----------|
| Backend runtime | Python 3.12, asyncio, Pydantic v2, SQLAlchemy 2 (async) |
| Frontend | Next.js 16, React 19, Tailwind 4, shadcn/ui |
| Desktop shell | Tauri 2 (WebView2 on Windows) |
| Relational DB | PostgreSQL 16 (prod, native Windows installer) + SQLite (dev/test) |
| Vector DB | Qdrant (Windows binary) |
| Knowledge graph | NetworkX (in-process) with optional Neo4j adapter |
| Message bus | In-process async event bus + optional Memurai (Redis-compatible) for multi-process |
| Agent bridges | Subprocess + JSON-RPC over stdin/stdout (Windows CreateProcess + Job Objects) |
| Windows services | NSSM + pywin32 |
| Windows scheduling | Windows Task Scheduler (via `schtasks` / COM API) |
| Windows sandboxing | Job Objects + AppContainer + WDAC policies |
| Containerization | Docker (optional, via Docker Desktop on Windows / WSL2) |
| License | Apache 2.0 |
| Primary OS | Windows 11 |
| Secondary OS | Linux (v1.1) |

## License

Apache License 2.0 — see [`LICENSE`](LICENSE).

## Contributing

Contribution guide, code of conduct, issue/PR templates, and SDK documentation land in **Phase 2**. Until then, this repository is in pre-alpha architecture review — no PRs will be accepted.
