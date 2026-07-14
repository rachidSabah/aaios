# Architecture Index

This directory contains the complete architecture specification for AAiOS. Read in order.

| # | Document | Purpose |
|---|----------|---------|
| 00 | [Executive Overview](00-overview.md) | What AAiOS is, why it exists, how the docs fit together. Start here. |
| 01 | [Goals & Principles](01-goals-and-principles.md) | The six non-negotiable design invariants and the trade-offs we explicitly accept. |
| 02 | [Generic Agent Runtime](02-generic-agent-runtime.md) | **The centerpiece.** `GenericAgent` interface, 16 agent types, capability-based selection, implementation-agnostic contracts. |
| 03 | [System Design](03-system-design.md) | The kernel, the Task Orchestrator (queue/DAG/checkpoint/resume/scheduling/approval gates), the supervisor-as-agent loop, e2e flow. |
| 04 | [Component Map](04-component-map.md) | Every named component — responsibility, owns, depends on, exposes, failure modes. |
| 05 | [Data Flow](05-data-flow.md) | Four end-to-end scenarios — all written against agent *types*, not product names. |
| 06 | [Tech Stack](06-tech-stack.md) | Locked technology choices (Windows-first), rationale, rejected alternatives. |
| 07 | [Security Model](07-security-model.md) | Zero-trust, RBAC+ABAC, Windows sandboxing, secrets with rotation, audit, permission flow, least-privilege. |
| 08 | [Deployment Topology](08-deployment-topology.md) | Windows-native deployment (Services + Task Scheduler), optional Docker, Linux compat path. |
| 09 | [Roadmap](09-roadmap.md) | The 14-phase build plan with entry/exit criteria per phase. |

## Quick navigation by role

- **Engineer** → 02 → 03 → 04 → the component you are implementing
- **Agent SDK author** → 02 → 09 (Phase 11)
- **Security reviewer** → 07 → trace back to referenced components
- **DevOps / Windows operator** → 08 → 06
- **Product / exec** → 00 → 09

## Core design principles (in precedence order)

1. **Genericism over convenience** — orchestrate capabilities, not products.
2. **Modularity over performance** — typed interfaces, strict layering.
3. **Supervision over autonomy** — agents propose, supervisor disposes.
4. **Observability over speed** — every operation is an event, persisted, replayable.
5. **Zero-trust over convenience** — minimum privileges, permission-gated, audited.
6. **Windows-first over cross-platform shortcuts** — Windows 11 native first, Linux via abstraction layer.

## Diagrams

All diagrams are written as Mermaid in the source markdown files (renders natively on GitHub). Standalone `.mmd` sources for the highest-value diagrams will be added in Phase 2 alongside a PNG export pipeline.

## Key invariants

- **INV-09**: No code outside `agents/_impls/<name>/` references a specific agent implementation by name. Enforced by CI regex ban. This is the guarantee that makes the system future-proof.
- **INV-10**: Every `GenericAgent` implementation satisfies the 11-method interface. Enforced by mypy + interface tests.
- **INV-02**: All I/O goes through the Gateway. No `subprocess` / `open` / `httpx` / `socket` outside `core/gateway/`.
