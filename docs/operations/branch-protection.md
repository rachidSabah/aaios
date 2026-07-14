# Branch Protection — `main`

> **Phase 2 deliverable.** Apply these rules to `main` after the first push to GitHub.

## Required rules

Configure on GitHub under **Settings → Branches → Branch protection rules → Add rule**:

### Branch name pattern
`main`

### Protect matched branches
- [x] **Require a pull request before merging**
  - Required approving reviews: **1** (bump to 2 post-v1)
  - Dismiss stale pull request approvals when new commits are pushed: **yes**
  - Require review from Code Owners: **yes**
  - Restrict who can dismiss pull request reviews: **admins only**
- [x] **Require status checks to pass before merging**
  - Require branches to be up to date before merging: **yes**
  - Required status checks (must pass on **both** Windows and Linux):
    - `Python (windows-latest, 3.12)`
    - `Python (ubuntu-latest, 3.12)`
    - `Web (Next.js)`
    - `Architecture invariants`
    - `All checks required`
- [x] **Require conversation resolution before merging** — yes
- [x] **Do not allow bypassing the above settings** — yes (no admins, no force pushes, no deletions)

### Rules applied to administrators
- [x] **Restrict who can push to matching branches** — `rachidSabah` only (until v1.0; open up to a maintainers team post-v1)
- [x] **Allow force pushes** — **NO**
- [x] **Allow deletions** — **NO**

### Tag protection
Tags matching `v*` can only be pushed by `rachidSabah` (or by the GitHub Actions release workflow using `GITHUB_TOKEN`).

## Secret scanning

Under **Settings → Code security**:

- [x] **Secret scanning** — enabled
- [x] **Push protection** — enabled (blocks commits containing secrets)
- [x] **Scan on push** — enabled

## Code scanning

- [x] **CodeQL** — enabled (see `.github/workflows/codeql.yml`)
- [ ] **Snyk Code** (optional, future)

## Dependabot

- [x] **Dependabot security updates** — enabled
- [x] **Dependabot version updates** — enabled (see `.github/dependabot.yml`)

## Workflow permissions

Under **Settings → Actions → General → Workflow permissions**:

- Read and write permissions (for the release workflow)
- Allow GitHub Actions to create and approve pull requests: **yes** (for Dependabot auto-merge post-v1)

## After v1.0

- Bump required reviews from 1 to 2
- Require the `tests-pass` check on **both** Windows and Linux (matrix)
- Add a 24-hour merge-delay rule for security-sensitive paths (`core/gateway/`, `services/security/`)
- Create a `maintainers` team and let it dismiss reviews
