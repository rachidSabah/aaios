# Architecture Index

This directory contains the complete architecture specification for AAiOS. Read in order.

| # | Document | Purpose |
|---|----------|---------|
| 00 | [Executive Overview](00-overview.md) | What AAiOS is, why it exists, how the docs fit together. Start here. |
| 01 | [Goals & Principles](01-goals-and-principles.md) | The five non-negotiable design invariants and the trade-offs we explicitly accept. |
| 02 | [System Design](02-system-design.md) | The kernel, the supervisor loop, the agent lifecycle, end-to-end flow. |
| 03 | [Component Map](03-component-map.md) | Every named component — responsibility, owns, depends on, exposes, failure modes. |
| 04 | [Data Flow](04-data-flow.md) | Four end-to-end scenarios: coding task, desktop task, RAG query, plugin install. |
| 05 | [Tech Stack](05-tech-stack.md) | Locked technology choices with rationale and rejected alternatives. |
| 06 | [Security Model](06-security-model.md) | Zero-trust, RBAC, sandboxing, secrets, audit, permission flow. **Most important doc.** |
| 07 | [Deployment Topology](07-deployment-topology.md) | Docker Compose layout, networking, volumes, runbook. |
| 08 | [Roadmap](08-roadmap.md) | The 12-phase build plan with entry/exit criteria per phase. |

## Quick navigation by role

- **Engineer** → 02 → 03 → the component you are implementing
- **Security reviewer** → 06 → trace back to referenced components
- **DevOps** → 07 → 05
- **Product / exec** → 00 → 08

## Diagrams

All diagrams are written as Mermaid in the source markdown files (renders natively on GitHub). Standalone `.mmd` sources for the highest-value diagrams will be added in Phase 2 alongside a PNG export pipeline.
