# Migration Guide — AAiOS v5.2 → v5.3

**Release:** v5.3.0 — Enterprise Research & Reasoning Platform
**Date:** 2026-07-16

---

## Overview

AAiOS v5.3.0 is a **purely additive** release. No existing APIs, CLI commands,
dashboard pages, or data formats have been removed or renamed. Upgrading from
v5.2 requires no code changes.

---

## What's New (Additive Only)

### Python API

New public module: `services/research/`

| Class | Purpose |
|---|---|
| `ResearchManager` | Top-level facade for the entire research platform |
| `ResearchEngine` | Phase 1 — projects, sessions, plans, tasks, pipelines, templates, memory, workspaces, timeline |
| `ResearchAgentOrganization` | Phase 2 — registry of 10 specialized agents |
| `MultiModelReasoningEngine` | Phase 3 — multi-model consensus and conflict detection |
| `EvidenceGraph` | Phase 4 — searchable graph of claims, facts, sources, documents, reports, sessions |
| `FactVerificationEngine` | Phase 5 — cross-source fact verification with reliability ranking |
| `KnowledgeSynthesisEngine` | Phase 6 — unified knowledge synthesis from multiple documents |

Plus 30+ dataclasses in `services/research/models.py`.

### REST API

13 new endpoints under `/api/v1/research/`:

- `GET /overview`
- `GET /projects`, `POST /projects`, `GET /projects/{id}`
- `GET /agents`
- `POST /agents/{type}/research`
- `POST /reasoning`
- `GET /evidence-graph`, `GET /evidence-graph/search`
- `POST /verification`
- `POST /synthesis`
- `GET /timeline`
- `GET /stats`

### CLI

New top-level command group:

```
aaios research [overview|projects|create-project|agents|research|reason|evidence|verify|synthesize|timeline|stats]
```

All commands accept `--format json|yaml|markdown|table`.

### Dashboard

New page: `/research` — linked from the top navigation.

---

## Upgrading

### Pip install

```bash
pip install --upgrade aaios==5.3.0
```

### From source

```bash
git pull
git checkout v5.3.0
pip install -e .
```

---

## Verification

After upgrading:

```bash
aaios version          # should print 5.3.0
aaios research overview
aaios research agents
aaios research research scientific "what is quantum entanglement?"
aaios research verify "the sky is blue"
```

---

## Key Design Principles

1. **Every conclusion contains evidence** — no bare claims
2. **Every claim has a confidence score** — explicit uncertainty
3. **Every export requires human approval** — `requires_approval=True` everywhere
4. **No intentional hallucination** — when evidence is missing, the engine
   says so explicitly and produces low-confidence output with documented
   limitations
5. **All services are read-only with respect to external systems** — they
   never publish or modify production data

---

## Rollback

To roll back to v5.2:

```bash
pip install aaios==5.2.0
```

No data migration is required in either direction. v5.3 does not change any
persistent storage format.

---

## Frequently Asked Questions

**Q: Does the research engine call real LLMs?**
A: The Multi-Model Reasoning engine accepts `ModelAnalysis` objects produced
elsewhere (e.g. by the existing ModelRouter). It does not call LLMs directly.
This keeps the engine testable and allows the existing provider infrastructure
to be reused.

**Q: Does the research engine access the internet?**
A: No. All engines are offline. Source material is supplied by the caller.
When source material is unavailable, agents return low-confidence findings
with explicit limitations and follow-up questions.

**Q: Can I disable the new features?**
A: Yes — simply don't call the new APIs or visit the new dashboard page. They
are lazily instantiated and consume no resources unless used.

**Q: Are there new infrastructure requirements?**
A: No. v5.3 runs on the same Python 3.12+ runtime as v5.2.

---

## Support

- Issues: https://github.com/rachidSabah/aaios/issues
- Discussions: https://github.com/rachidSabah/aaios/discussions
- Security: see `SECURITY.md`
