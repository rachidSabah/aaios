# 00 — Executive Architecture Overview

> **Audience:** all stakeholders (engineering, security, DevOps, product).
> **Purpose:** communicate *what* AAiOS is, *why* it is shaped this way, and *how* the rest of the architecture documents fit together.

---

## 1. What AAiOS is

Agentic AI Operating System (AAiOS) is a **self-hosted, modular runtime** that turns a collection of language models, automation agents, tool servers, and memory stores into a single, coherent, autonomous system. Instead of treating "an AI agent" as a single prompt → response loop, AAiOS treats it as an *operating environment*: there is a kernel (the Supervisor), a process model (Agents), a syscall layer (Tools + MCP), a filesystem (Memory), a package manager (Plugins), and a shell (CLI / Web UI / Desktop).

The mental model is intentional. Just as a conventional OS does not ask you to choose between the kernel and the userland, AAiOS does not ask you to choose between the LLM provider and the agent runtime. Every layer is swappable, every boundary is explicit, and every component speaks a typed contract.

## 2. Why a new system

The current landscape of "agentic AI" tools falls into three categories, each with a structural limitation that AAiOS is designed to address:

1. **Single-vendor copilots** (Cursor, GitHub Copilot Workspace, Devin). These are tightly coupled to one model provider and one workflow. They cannot be extended, self-hosted, or audited. AAiOS treats providers as pluggable and workflows as user-defined.
2. **Agent frameworks** (LangGraph, AutoGen, CrewAI). These are libraries — they give you primitives, but you still have to build the runtime, the memory, the security model, the dashboard, and the deployment story. AAiOS is the runtime, not the library.
3. **Desktop AI assistants** (ChatGPT desktop, Claude desktop). These are closed-source applications with limited automation. They do not expose their tool layer, their memory, or their plugin system. AAiOS exposes all three.

AAiOS is positioned at the intersection: a **complete operating environment** for agents, open-source, self-hostable, poly-model, and extensible by design.

## 3. Design philosophy in one paragraph

Every architectural choice in AAiOS is governed by five non-negotiable principles: **modularity** (every component has a typed interface and can be replaced), **supervision** (no agent action is final until the supervisor commits it), **observability** (every decision, tool call, and token is logged and replayable), **zero-trust** (no agent can do anything the user has not explicitly permitted), and **production-readiness** (no placeholder code, no toy examples, no "TODO in a future release"). These principles are expanded in [`01-goals-and-principles.md`](01-goals-and-principles.md).

## 4. High-level system shape

The system is organized as five concentric layers, each with a strict dependency direction (outer layers depend on inner layers, never the reverse):

```
┌─────────────────────────────────────────────────────────────────────┐
│  L5 — SURFACES     CLI • Web UI • Desktop App • REST/gRPC API       │
├─────────────────────────────────────────────────────────────────────┤
│  L4 — SUPERVISION  Planner • Agent Router • Reflection • QA • WFE   │
├─────────────────────────────────────────────────────────────────────┤
│  L3 — AGENTS       Claude Code • Hermes • Research • Browser …      │
├─────────────────────────────────────────────────────────────────────┤
│  L2 — SERVICES     Model Router • Memory • MCP • Plugins • Security │
├─────────────────────────────────────────────────────────────────────┤
│  L1 — KERNEL       Event Bus • State • Config • Logging • Registry  │
└─────────────────────────────────────────────────────────────────────┘
                            │
                            ▼
                  External Infra (DBs, LLMs, MCP, OS)
```

This layering is enforced at the import level — a build-time check (ruff custom rule, see Phase 2) prevents inner layers from importing outer layers. This is not aesthetic; it is what guarantees that the kernel can be reused by a completely different supervisor implementation, or that the supervisor can be embedded inside another product without dragging the web UI along.

## 5. Document map

The remaining architecture documents are organized as follows. Each is self-contained but assumes the previous one has been read.

| # | Document | What it covers |
|---|----------|----------------|
| 01 | [Goals & Principles](01-goals-and-principles.md) | The five non-negotiable principles, the design invariants, and the trade-offs we explicitly accept. |
| 02 | [System Design](02-system-design.md) | The kernel, the supervisor loop, the agent lifecycle, and the request → response flow with full Mermaid diagrams. |
| 03 | [Component Map](03-component-map.md) | Every named component from the brief — what it does, what it owns, what it depends on, and the contract it exposes. |
| 04 | [Data Flow](04-data-flow.md) | Four end-to-end scenarios: autonomous coding task, desktop automation task, RAG query, and plugin install. |
| 05 | [Tech Stack](05-tech-stack.md) | The locked technology choices with the rationale and the rejected alternatives. |
| 06 | [Security Model](06-security-model.md) | Zero-trust, RBAC, sandboxing, secret management, audit log, and permission approval flow. |
| 07 | [Deployment Topology](07-deployment-topology.md) | Docker Compose layout, networking, volumes, and the path to Kubernetes in the future. |
| 08 | [Roadmap](08-roadmap.md) | The 12-phase build plan with entry/exit criteria for each phase. |

## 6. What is explicitly out of scope

To prevent scope creep, the following are **explicitly excluded** from AAiOS v1, even though they would be natural extensions:

- **Mobile native apps.** The web UI is responsive; native iOS/Android clients are deferred to a v2.
- **Multi-tenant SaaS mode.** AAiOS is designed for single-tenant self-hosting. Multi-tenant mode requires a control plane that is out of scope for v1.
- **Federated learning / on-device training.** AAiOS consumes models; it does not train them.
- **Realtime voice conversation.** Voice input/output is supported as a plugin, but a low-latency voice mode is not a v1 deliverable.
- **GPU scheduling.** AAiOS assumes that model inference happens at provider endpoints (cloud or local Ollama). Local GPU scheduling is the responsibility of Ollama / LM Studio.

These exclusions are revisitable. Each is documented in [`01-goals-and-principles.md`](01-goals-and-principles.md) under "Deferred decisions."

## 7. How to read this architecture

If you are an **engineer**, start at [`02-system-design.md`](02-system-design.md) and follow the links to the component you are implementing. If you are a **security reviewer**, jump to [`06-security-model.md`](06-security-model.md) and trace back to the components it references. If you are a **DevOps engineer**, start at [`07-deployment-topology.md`](07-deployment-topology.md). If you are a **product or exec stakeholder**, this document plus [`08-roadmap.md`](08-roadmap.md) is sufficient.

Every claim in this document is backed by a more detailed section elsewhere in the architecture. If you find a claim that is not, that is a defect — open an issue labeled `architecture-gap`.
