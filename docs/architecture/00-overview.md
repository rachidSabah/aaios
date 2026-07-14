# 00 — Executive Architecture Overview

> **Audience:** all stakeholders (engineering, security, DevOps, product).
> **Purpose:** communicate *what* AAiOS is, *why* it is shaped this way, and *how* the rest of the architecture documents fit together.

---

## 1. What AAiOS is

Agentic AI Operating System (AAiOS) is a **Windows-first, modular runtime** that turns a collection of language models, automation agents, tool servers, and memory stores into a single, coherent, autonomous system. Instead of treating "an AI agent" as a single prompt → response loop, AAiOS treats it as an *operating environment*: there is a kernel, a Generic Agent Runtime (the process model), a Task Orchestrator (the scheduler), a Tool + MCP layer (the syscall surface), a Memory subsystem (the filesystem), a Plugin Manager (the package manager), and a CLI / Web UI / Desktop App (the shell).

The mental model is intentional. Just as a conventional OS does not ask you to choose between the kernel and the userland, AAiOS does not ask you to choose between the LLM provider and the agent runtime. Every layer is swappable, every boundary is explicit, and every component speaks a typed contract.

**Critical design principle:** AAiOS is built around a **Generic Agent Runtime**, not around any specific AI product. Claude Code and Hermes are first-class *examples* of agent implementations, but they are not architectural dependencies. The system can swap Claude Code for OpenHands, Cline, Roo Code, Gemini CLI, Codex CLI, or any future coding agent — without modifying the Supervisor, the Task Orchestrator, the Memory, the Dashboard, or any other core component. The same is true for Hermes and any future desktop agent.

## 2. Why a new system

The current landscape of "agentic AI" tools falls into three categories, each with a structural limitation that AAiOS is designed to address:

1. **Single-vendor copilots** (Cursor, GitHub Copilot Workspace, Devin). Tightly coupled to one model and one workflow. Cannot be extended, self-hosted, or audited. AAiOS treats providers and agents as pluggable and workflows as user-defined.
2. **Agent frameworks** (LangGraph, AutoGen, CrewAI). Libraries that give you primitives, but you still have to build the runtime, memory, security, dashboard, and deployment story. AAiOS is the runtime, not the library.
3. **Desktop AI assistants** (ChatGPT desktop, Claude desktop). Closed-source applications with limited automation. They do not expose their tool layer, their memory, or their plugin system. AAiOS exposes all three.

AAiOS is positioned at the intersection: a **complete operating environment** for agents, open-source, Windows-first, self-hostable, poly-model, poly-agent, and extensible by design.

## 3. Design philosophy in one paragraph

Every architectural choice in AAiOS is governed by six non-negotiable principles: **modularity** (every component has a typed interface and can be replaced), **genericism** (the system orchestrates capabilities, not products — no agent name is hardcoded anywhere in the core), **supervision** (no agent action is final until the supervisor commits it), **observability** (every decision, tool call, and token is logged and replayable), **zero-trust** (no agent can do anything the user has not explicitly permitted), and **Windows-first** (the system is built and tested on Windows 11 first; Linux is a first-class but secondary target). These principles are expanded in [`01-goals-and-principles.md`](01-goals-and-principles.md).

## 4. High-level system shape

The system is organized as five concentric layers, each with a strict dependency direction (outer layers depend on inner layers, never the reverse):

```
┌─────────────────────────────────────────────────────────────────────┐
│  L5 — SURFACES     CLI • Web UI • Desktop App • REST/WebSocket API  │
├─────────────────────────────────────────────────────────────────────┤
│  L4 — SUPERVISION  SupervisorAgent • Task Orchestrator • WFE        │
│         (Capability Selector, Approval Gates, Checkpointing)         │
├─────────────────────────────────────────────────────────────────────┤
│  L3 — AGENTS       GenericAgent implementations                    │
│         CodingAgent (Claude Code, future: OpenHands, Cline, …)      │
│         DesktopAgent (Hermes, future: AHK, pywinauto, …)            │
│         Planner, Reflection, QA, Research, Browser, Memory,         │
│         Security, Deployment, Vision, Voice, Document, Workflow      │
├─────────────────────────────────────────────────────────────────────┤
│  L2 — SERVICES     Model Router • Memory • MCP • Plugins • Security │
│         Permission Manager • Agent Registry                         │
├─────────────────────────────────────────────────────────────────────┤
│  L1 — KERNEL       Event Bus • State • Config • Logging • Telemetry │
│         DI • Tool Registry • Prompt Registry • Gateway (I/O)        │
└─────────────────────────────────────────────────────────────────────┘
                            │
                            ▼
        Windows 11 (primary) / Linux (v1.1) + External Infra
        (Postgres, Qdrant, LLM providers, MCP servers, OS desktop)
```

This layering is enforced at the import level — a build-time check (ruff custom rule, see Phase 2) prevents inner layers from importing outer layers. This is not aesthetic; it is what guarantees that the kernel can be reused by a completely different supervisor implementation, or that the Generic Agent Runtime can be embedded inside another product without dragging the web UI along.

**The Generic Agent Runtime is the architectural centerpiece.** It is documented in [`02-generic-agent-runtime.md`](02-generic-agent-runtime.md) — read it before any other implementation doc.

## 5. Document map

The architecture documents are organized as follows. Each is self-contained but assumes the previous one has been read.

| # | Document | What it covers |
|---|----------|----------------|
| 00 | [Executive Overview](00-overview.md) | This document. |
| 01 | [Goals & Principles](01-goals-and-principles.md) | The six non-negotiable principles, the design invariants, and the trade-offs we explicitly accept. |
| 02 | [Generic Agent Runtime](02-generic-agent-runtime.md) | **The centerpiece.** `GenericAgent` interface (11 methods), 16 agent types, capability manifests, capability-based selection, implementation-agnostic contracts. |
| 03 | [System Design](03-system-design.md) | The kernel, the Task Orchestrator (queue/DAG/checkpoint/resume/scheduling/approval gates), the supervisor-as-agent loop, e2e flow. |
| 04 | [Component Map](04-component-map.md) | Every named component — what it does, what it owns, what it depends on, and the contract it exposes. |
| 05 | [Data Flow](05-data-flow.md) | Four end-to-end scenarios, all written against agent *types* (CodingAgent, DesktopAgent), not product names. |
| 06 | [Tech Stack](06-tech-stack.md) | Locked technology choices (Windows-first), rationale, rejected alternatives. |
| 07 | [Security Model](07-security-model.md) | Zero-trust, RBAC+ABAC, sandboxing (Windows Job Objects/AppContainer/WDAC), secrets with rotation, audit, permission flow, least-privilege enforcement. |
| 08 | [Deployment Topology](08-deployment-topology.md) | Windows-native deployment (Services + Task Scheduler), optional Docker Compose, Linux compat path. |
| 09 | [Roadmap](09-roadmap.md) | The 14-phase build plan with entry/exit criteria per phase. |

## 6. What is explicitly out of scope for v1

- **Multi-tenant SaaS mode.** Single-tenant self-hosting only.
- **Linux as primary target.** Linux is a v1.1 goal. The architecture is Linux-ready (abstraction layer in place) but Linux adapters are stubbed in v1.
- **Native mobile clients.** Responsive web only.
- **Realtime voice conversation.** Voice agent interface exists; sub-300ms voice mode is post-v1.
- **Local GPU scheduling.** We rely on Ollama / LM Studio for this.
- **Federated identity (SAML, SCIM).** OAuth + API keys in v1.
- **Workflow marketplace.** Plugin marketplace in v1; signed workflow bundles are v1.1.

These exclusions are revisitable. Each is documented in [`01-goals-and-principles.md`](01-goals-and-principles.md) under "Deferred decisions."

## 7. How to read this architecture

- **Engineer** → start at [`02-generic-agent-runtime.md`](02-generic-agent-runtime.md), then [`03-system-design.md`](03-system-design.md), then [`04-component-map.md`](04-component-map.md), then the component you are implementing.
- **Security reviewer** → jump to [`07-security-model.md`](07-security-model.md) and trace back to the components it references.
- **DevOps / Windows operator** → start at [`08-deployment-topology.md`](08-deployment-topology.md).
- **Product / exec stakeholder** → this document plus [`09-roadmap.md`](09-roadmap.md) is sufficient.

Every claim in this document is backed by a more detailed section elsewhere in the architecture. If you find a claim that is not, that is a defect — open an issue labeled `architecture-gap`.
