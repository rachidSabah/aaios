<p align="center">
  <img src="docs/aaios-banner.svg" alt="AAiOS — Agentic AI Operating System" width="800" />
</p>

<p align="center">
  <img src="docs/aaios-dashboard-preview.svg" alt="AAiOS Dashboard" width="100%" />
</p>

# Agentic AI Operating System (AAiOS)

> A **Windows-first**, modular, production-grade operating system for autonomous AI agents — orchestrating multiple LLM providers, multiple **generic** agents, MCP servers, vector memory, knowledge graphs, plugins, and workflows behind a single supervisor. Built around a **Generic Agent Runtime** where Claude Code, Hermes, and any future agent (OpenHands, Cline, Roo Code, Gemini CLI, Codex CLI, custom) are all just replaceable implementations.

[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)
[![Status: v5.3.0 Released](https://img.shields.io/badge/Status-v5.3.0%20Released-brightgreen)](https://github.com/rachidSabah/aaios/releases)
[![Python 3.12+](https://img.shields.io/badge/Python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![Next.js 16](https://img.shields.io/badge/Next.js-16-black.svg)](https://nextjs.org/)
[![Windows 11](https://img.shields.io/badge/Platform-Windows%2011%20first-blue.svg)](https://www.microsoft.com/windows/)
[![Tests: 1220 passing](https://img.shields.io/badge/Tests-1220%20passing-brightgreen)]()
[![Ruff](https://img.shields.io/badge/Ruff-clean-brightgreen)]()
[![Mypy --strict](https://img.shields.io/badge/Mypy-strict%20clean-brightgreen)]()

---

## One-Click Install

### Windows 11 (PowerShell)

```powershell
irm https://raw.githubusercontent.com/rachidSabah/aaios/main/deploy/windows/install.ps1 | iex
```

### WSL2 / Linux (Bash)

```bash
curl -fsSL https://raw.githubusercontent.com/rachidSabah/aaios/main/deploy/wsl/install.sh | bash
```

Both scripts auto-install all dependencies (Python 3.12, Node.js 22, pnpm, git), clone the repo, set up the virtual environment, **detect and bind AI agents** (Claude Code CLI + Hermes daemon — auto-installs if not found), run `aaios doctor` to verify, and then **offer to start AAiOS immediately in LIVE mode**.

After install, start AAiOS anytime with:
```bash
aaios start
```

This boots the kernel, security, model router, memory, agent registry, orchestrator, supervisor, and the API server — all in real mode, no mock, no demo.

### One-Click Uninstall

**Windows 11:**
```powershell
irm https://raw.githubusercontent.com/rachidSabah/aaios/main/deploy/windows/uninstall.ps1 | iex
```

**WSL2 / Linux:**
```bash
curl -fsSL https://raw.githubusercontent.com/rachidSabah/aaios/main/deploy/wsl/uninstall.sh | bash
```

Or via CLI:
```bash
aaios uninstall                          # basic (keeps config/data)
aaios uninstall --remove-data            # also delete config/data/logs
aaios uninstall --remove-data --remove-agents  # nuke everything including agent CLIs
```

System dependencies (Python, Node.js, git) are NOT removed.

### Auto-Update

AAiOS can automatically pull new commits from GitHub:

```bash
aaios update                 # check + update once
aaios update --check         # just check, don't update
aaios update --auto          # background loop (checks every 30 min)
aaios update --auto -i 60    # check every 60 min
```

The auto-update pulls new commits, reinstalls Python + Node packages, and re-binds agents — all without downtime. Run `aaios update --auto` in a background terminal or as a scheduled task.

### Claude Code via Proxy (Free Models)

If you're running Claude Code through a proxy (not the official Anthropic API), set the proxy URL before installing:

```bash
# WSL/Linux
export ANTHROPIC_BASE_URL=http://localhost:8080/v1
export ANTHROPIC_API_KEY=your-proxy-key
curl -fsSL https://raw.githubusercontent.com/rachidSabah/aaios/main/deploy/wsl/install.sh | bash
```

```powershell
# Windows
$env:ANTHROPIC_BASE_URL = "http://localhost:8080/v1"
$env:ANTHROPIC_API_KEY = "your-proxy-key"
irm https://raw.githubusercontent.com/rachidSabah/aaios/main/deploy/windows/install.ps1 | iex
```

AAiOS will auto-detect the proxy URL and configure the Claude Code agent to use it instead of the official Anthropic API.

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
| 1 | ✅ Complete | Architecture design — Generic Agent Runtime, 16 agent types, Windows-first, 10 architecture docs |
| 2 | ✅ Complete | Repository structure, GitHub scaffolding, Windows+Linux CI matrix |
| 3 | ✅ Complete | Core framework (kernel + Gateway + platform adapters) |
| 4 | ✅ Complete | Generic Agent Runtime + Agent Registry |
| 5 | ✅ Complete | Task Orchestrator (queue, DAG, checkpoint, resume, scheduling, approval gates) |
| 6 | ✅ Complete | Model Router (13 providers with failover, cost tracking, rate limiting) |
| 7 | ✅ Complete | Memory subsystem (vector, graph, RAG, compression, context windows) |
| 8 | ✅ Complete | Supervisor + Planner + Reflection + QA + Security Layer |
| 9 | ✅ Complete | First CodingAgent (Claude Code) — subprocess bridge + JSON-RPC + sandbox |
| 10 | ✅ Complete | First DesktopAgent (Hermes) — 14 capabilities (desktop + browser) |
| 11 | ✅ Complete | Plugins + MCP + Plugin/Agent SDK + 3 example plugins |
| 12 | ✅ Complete | Dashboard + CLI + API (30 routes, 12 CLI commands, Next.js dashboard) |
| 13 | ✅ Complete | Testing matrix (597 tests: unit, integration, e2e, stress, performance, security) |
| 14 | ✅ Complete | Windows deployment + CI/CD + documentation + v5.1.0 release |
| 15 | ✅ Complete | v4.0 Execution Engine (16 domains) + v4.1 Production Approvals + Persistent Audit |
| 16 | ✅ Complete | v5.0 Cognitive Intelligence + v5.1 Knowledge Platform + v5.2 Engineering Intelligence |
| 17 | ✅ Complete | v5.2 Part 1B-2: Engineering Review Engine (12 review types) |
| 18 | ✅ Complete | v5.2 Part 1B-2: Test Intelligence Engine |
| 19 | ✅ Complete | v5.2 Part 1B-2: Documentation Intelligence |
| 20 | ✅ Complete | v5.2 Part 1B-2: Repository Evolution Engine |
| 21 | ✅ Complete | v5.2 Part 1B-2: Release Readiness Engine |
| 22 | ✅ Complete | v5.2 Part 1B-2: Developer Productivity Engine (DORA metrics) |
| 23 | ✅ Complete | v5.2 Part 1B-2: Repository Health Center (8 dimensions) |
| 24 | ✅ Complete | v5.2 Part 1B-2: Dashboard Integration (8 new pages) |
| 25 | ✅ Complete | v5.2 Part 1B-2: CLI Integration (10 new command groups) |
| 26 | ✅ Complete | v5.2 Part 1B-2: API Integration (22 new endpoints) — **1138 tests passing** |
| 27 | ✅ Complete | v5.3 Part 1A: Enterprise Research Engine (projects, sessions, plans, tasks, pipelines, templates, memory, workspaces, timeline) |
| 28 | ✅ Complete | v5.3 Part 1A: Multi-Agent Research (10 specialized agents) |
| 29 | ✅ Complete | v5.3 Part 1A: Multi-Model Reasoning (consensus, conflict detection, minority opinions) |
| 30 | ✅ Complete | v5.3 Part 1A: Evidence Graph (6 node types, 5 edge types, searchable) |
| 31 | ✅ Complete | v5.3 Part 1A: Fact Verification (5-tier source reliability, verification reports) |
| 32 | ✅ Complete | v5.3 Part 1A: Knowledge Synthesis (9 standard sections) — **1220 tests passing** |

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


## AAiOS v2.0 — Production Engineering Pass

v2.0 builds on v1.0 with five new agents and a full production engineering pass:

| Agent | What it does |
|---|---|
| **Supervisor Intelligence** | Adaptive routing, persistent planning, multi-agent delegation, autonomous jobs |
| **Dashboard** | Visual workflow builder, live monitoring, analytics (cost, latency, throughput) |
| **Windows Native** | Services, Job Objects, AppContainer, WDAC, Task Scheduler |
| **Provider Validation** | Live API verification for all 13 LLM providers |
| **Distributed Runtime** | Multi-machine orchestration with heartbeats, scatter/gather |
| **Voice & Vision** | Native multimodal: ASR, TTS, image understanding, image generation |

### Production Certification (12 phases)
- 22/22 subsystems validated
- 11/11 cluster tests passed
- 20/20 load tests passed (up to 10,000 simultaneous tasks)
- 8/8 chaos tests passed
- 6/6 security checks passed (Bandit, pip-audit, secret scan, SBOM)
- 8/8 Windows certification tests passed
- 10/10 dashboard certification tests passed

See `download/release/` for full per-phase reports.
