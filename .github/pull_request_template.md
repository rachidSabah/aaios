## Summary

<!-- One paragraph: what does this PR do and why? -->

## Type of change

- [ ] `feat` — new feature
- [ ] `fix` — bug fix
- [ ] `docs` — documentation only
- [ ] `refactor` — no behavior change
- [ ] `test` — tests only
- [ ] `chore` / `build` / `ci` — tooling
- [ ] `perf` — performance improvement
- [ ] **Breaking change** — requires a major version bump once v1.0 is out

## Architecture alignment

<!-- Which architecture document(s) does this touch? Did it require an
     architecture proposal first? -->

## Roadmap phase

<!-- Which phase (1-14) does this fall under? See docs/architecture/09-roadmap.md. -->

Phase: <!-- e.g. "Phase 4 — Generic Agent Runtime" -->

## Invariant checklist

<!-- The CI enforces these, but please self-check before requesting review. -->

- [ ] **INV-01** — Layer dependencies flow inward only (L5 → L1)
- [ ] **INV-02** — No `subprocess` / `open` / `httpx` / `socket` outside `core/gateway/`
- [ ] **INV-03** — Pydantic models only; no bare dicts across module boundaries
- [ ] **INV-04** — Events persisted before side effects
- [ ] **INV-05** — No secrets in code / configs / logs / error messages
- [ ] **INV-09** — No agent implementation names (`claude`, `hermes`, `openhands`, `cline`, `roo`, `gemini`, `codex`) in `core/`, `services/`, `supervisor/`, `orchestrator/`, `surfaces/`
- [ ] **INV-10** — Every `GenericAgent` implementation satisfies the 11-method interface
- [ ] **INV-12** — Tests pass on both `windows-latest` and `ubuntu-latest`

## Test coverage

- [ ] New code has unit tests
- [ ] New code has integration tests (if it crosses module boundaries)
- [ ] Coverage on touched files is ≥85%
- [ ] `pytest --offline` passes (no network needed)
- [ ] Tests added for any new `GenericAgent` implementation

## Documentation

- [ ] Public API has docstrings
- [ ] Updated `CHANGELOG.md` under `Unreleased`
- [ ] Updated `docs/architecture/` if the architecture changed (rare — open an architecture proposal first)
- [ ] Updated `docs/operations/` or `docs/developer/` if behavior changed

## Security

- [ ] No new dependencies with Critical or High CVEs
- [ ] `gitleaks` passes (no secrets in code)
- [ ] `bandit` passes (no new security warnings)
- [ ] If new permissions are introduced: documented in `07-security-model.md` and added to the permission catalog
- [ ] If new secrets are introduced: rotation policy defined

## Commit conventions

- [ ] Commits follow [Conventional Commits](https://www.conventionalcommits.org/) (`feat(scope): subject`)
- [ ] PR will be squash-merged; the PR title is the final commit message

## Reviewer checklist

<!-- For reviewers. Leave blank. -->

- [ ] CI green on both Windows and Linux
- [ ] Architecture invariants preserved
- [ ] Tests are meaningful (not just coverage-padding)
- [ ] No placeholder code (`pass`, `TODO` without issue, `NotImplementedError`)
- [ ] CHANGELOG updated
- [ ] At least one CODEOWNER approval
