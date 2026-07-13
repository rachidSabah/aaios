# Security Policy

AAiOS is designed with a zero-trust security model (see
[`docs/architecture/07-security-model.md`](docs/architecture/07-security-model.md)).
This document describes how to report vulnerabilities and what to expect.

## Supported versions

| Version | Supported |
|---------|-----------|
| `0.1.x` (pre-alpha) | ✅ security fixes only — no API stability guarantee |
| `< 0.1` | ❌ not supported |
| `>= 1.0` (future) | ✅ latest minor only |

Until v1.0.0, the API and on-disk formats may change without notice. Security
fixes will be backported to the latest `0.1.x` patch release.

## Reporting a vulnerability

**Please do NOT open a public GitHub issue for security vulnerabilities.**

Instead, report vulnerabilities via one of these channels (in priority order):

1. **GitHub Security Advisories** (preferred):
   - Go to <https://github.com/rachidSabah/aaios/security/advisories/new>
   - Click "Report a vulnerability"
   - Fill in the template

2. **Email**: send an encrypted email to **security@aaios.dev**
   (PGP key published at <https://keys.openpgp.org> once Phase 2 completes;
   until then, send plain email with the subject `SECURITY: <one-line summary>`).

Please include in your report:

- Description of the vulnerability and its impact
- Affected versions (use `aaios version` to confirm)
- Steps to reproduce (proof of concept if possible)
- Affected components (which `core/` / `services/` / `agents/` package)
- Suggested fix if you have one
- Whether you have already disclosed this to anyone else

## Response timeline

| Step | Target |
|------|--------|
| Acknowledge receipt | within 48 hours |
| Initial assessment (valid / invalid / needs more info) | within 5 business days |
| Fix development (for valid Critical / High) | within 30 days |
| Coordinated disclosure (with reporter) | 90-day window, negotiable |
| Public advisory + patched release | simultaneously |

We follow the [GitHub Security Advisory](https://docs.github.com/en/code-security/security-advisories)
workflow. If you prefer, you can request a CVE through GitHub's CVE pool once
the advisory is published.

## Scope

**In scope:**

- Any vulnerability in AAiOS code under `core/`, `services/`, `agents/`,
  `supervisor/`, `orchestrator/`, `surfaces/` (excluding `surfaces/web`).
- Vulnerabilities in `surfaces/web` that lead to XSS, CSRF, or auth bypass.
- Privilege escalation via the sandbox (plugin, agent, MCP).
- Audit log tampering or bypass.
- Secret store compromise.
- Bypass of the Gateway (e.g., an agent achieving I/O outside the Gateway).

**Out of scope (but please still report):**

- Vulnerabilities in third-party dependencies — report upstream, and we'll
  bump the dep + backport the fix.
- Vulnerabilities that require the user to deliberately disable security
  features (e.g., running with `--no-sandbox`).
- Self-XSS or social engineering.
- Theoretical timing side-channels with no demonstrated impact.
- Denial of service requiring more than 1 Gbps of traffic.

## Safe harbor

We will not pursue legal action against security researchers who:

- Make a good-faith effort to avoid privacy violations, destruction of data,
  or interruption or degradation of AAiOS services.
- Give us reasonable time to remediate before public disclosure.
- Do not demand a bounty as a condition of disclosure (AAiOS is unfunded
  open-source; there is no bug bounty program at this time).

## Hardening checklist (for operators)

Before deploying AAiOS in production, review and apply the security baseline
in [`docs/architecture/08-deployment-topology.md`](docs/architecture/08-deployment-topology.md)
§11. In particular:

- Generate a strong master key passphrase and back it up offline.
- Configure TLS (do not run on plain HTTP).
- Configure OAuth (do not run in local mode for multi-user).
- Configure the egress allow-list.
- Enable Windows Defender Controlled Folder Access for the data directory.
- Apply a WDAC policy restricting agent binaries (enterprise).
- Run `aaios doctor` and resolve all warnings.
