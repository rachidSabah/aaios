# Migration Guide — AAiOS v5.1 → v5.2

**Release:** v5.2.0 — Autonomous Software Engineering Platform
**Date:** 2026-07-16

---

## Overview

AAiOS v5.2.0 is a **purely additive** release. No existing APIs, CLI commands,
dashboard pages, or data formats have been removed or renamed. Upgrading from
v5.1 requires no code changes.

---

## What's New (Additive Only)

### Python API

New public modules under `services.engineering/`:

| Module | Purpose |
|---|---|
| `review_engine.py` | EngineeringReviewEngine (12 review types) |
| `test_intelligence.py` | TestIntelligenceEngine |
| `documentation_intelligence.py` | DocumentationIntelligenceEngine |
| `evolution_engine.py` | RepositoryEvolutionEngine |
| `release_readiness.py` | ReleaseReadinessEngine |
| `productivity_engine.py` | DeveloperProductivityEngine |
| `health_center.py` | RepositoryHealthCenter |

New gateway:

| Module | Purpose |
|---|---|
| `core/gateway/git.py` | GitGateway — read-only git operations (INV-02 compliant) |

The `EngineeringManager` facade (existing since v5.2 Part 1A) now wires these
new engines as attributes: `mgr.review_engine`, `mgr.test_intelligence`,
`mgr.documentation`, `mgr.evolution`, `mgr.release_readiness_engine`,
`mgr.productivity`, `mgr.health_center`. New methods: `review()`,
`review_all()`, `test_suite_analysis()`, `test_coverage()`, `test_risk()`,
`documentation_analysis()`, `documentation_recommendations()`,
`evolution_timeline()`, `evolution_dashboard()`, `evolution_report()`,
`release_readiness()`, `certification_report()`, `productivity_metrics()`,
`productivity_dora()`, `productivity_dashboard()`, `productivity_report()`,
`record_productivity_event()`, `health()`, `health_quick_score()`.

### REST API

New endpoints under `/api/v1/engineering/`:

- `POST /reviews` — run all 12 reviews
- `POST /reviews/{type}` — run a single review
- `GET /reviews/types` — list supported review types
- `GET /test-intelligence/analysis`
- `GET /test-intelligence/coverage`
- `POST /test-intelligence/risk`
- `GET /documentation/analysis`
- `GET /documentation/recommendations`
- `GET /repository/evolution`
- `GET /repository/timeline`
- `GET /repository/analysis`
- `POST /release/readiness`
- `POST /release/certification`
- `GET /productivity/dashboard`
- `GET /productivity/metrics`
- `GET /productivity/dora`
- `POST /productivity/events`
- `GET /productivity/report`
- `GET /health`
- `GET /health/score`
- `POST /planning/create`
- `POST /planning/impact`

All endpoints accept and return JSON. OpenAPI schema is auto-generated at
`/docs`.

### CLI

New top-level command groups:

```
aaios engineering [overview|agents|test-intelligence|productivity]
aaios architecture [recommendations]
aaios review [run|all]
aaios metrics [show]
aaios repository [analyze|evolution|timeline]
aaios release [readiness|certify]
aaios health [show]
aaios documentation [analyze|recommendations]
aaios dependencies [review]
aaios planning [create|impact]
```

All commands accept `--format json|yaml|markdown|table`.

### Dashboard

New pages linked from the top navigation:

- `/engineering`
- `/repository`
- `/architecture`
- `/reviews`
- `/test-intelligence`
- `/release-readiness`
- `/repository-health`
- `/features`
- `/dependencies`

All pages honor the existing dark/light theme via CSS variables.

---

## Upgrading

### Pip install

```bash
pip install --upgrade aaios==5.2.0
```

### From source

```bash
git pull
git checkout v5.2.0
pip install -e .
```

### Optional dependencies

If you use the test intelligence coverage report feature, install:

```bash
pip install defusedxml
```

If you use the YAML output format in the CLI, install:

```bash
pip install pyyaml
```

Both are optional — the engines degrade gracefully without them.

---

## Verification

After upgrading, verify your installation:

```bash
aaios version          # should print 5.2.0
aaios engineering overview
aaios health show
aaios release readiness --version 5.2.0
```

---

## Rollback

To roll back to v5.1:

```bash
pip install aaios==5.1.0
```

No data migration is required in either direction. v5.2 does not change any
persistent storage format.

---

## Frequently Asked Questions

**Q: Does v5.2 modify my code automatically?**
A: No. Every recommendation requires human approval. Every engine is read-only.

**Q: Do the new engines access the network?**
A: No. All engines are offline. The evolution engine uses git locally via the
GitGateway; no remote git operations are performed.

**Q: Can I disable the new features?**
A: Yes — simply don't call the new APIs or visit the new dashboard pages. They
are lazily instantiated and consume no resources unless used.

**Q: Are there new infrastructure requirements?**
A: No. v5.2 runs on the same Python 3.12+ runtime as v5.1.

---

## Support

- Issues: https://github.com/rachidSabah/aaios/issues
- Discussions: https://github.com/rachidSabah/aaios/discussions
- Security: see `SECURITY.md`
