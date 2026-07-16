# AAiOS v5.3.1 LTS — Support Policy

## LTS Support

**AAiOS v5.3.1-LTS** is a Long-Term Support release.

- **Released:** 2026-07-16
- **Initial support end:** 2027-07-16 (12 months)
- **Extended support end:** 2028-07-16 (24 months, security fixes only)
- **Status:** Production-ready

## What LTS Means

- ✅ Bug fixes: yes
- ✅ Security patches: yes
- ✅ Critical regressions: yes
- ❌ New features: no
- ❌ Breaking changes: no
- ❌ Experimental APIs: no

## Support Tiers

### Tier 1 — Critical (24h response)
- Security vulnerabilities (CVE-scored)
- Data loss or corruption
- Production outages

### Tier 2 — High (72h response)
- Functional regressions
- Performance regressions > 50%
- Documentation errors affecting production

### Tier 3 — Medium (1 week response)
- Minor bugs
- Documentation improvements
- Feature requests (deferred to next minor)

## Reporting Issues

- **Security issues:** See [SECURITY.md](SECURITY.md) — do NOT file public issues
- **Bugs:** [GitHub Issues](https://github.com/rachidSabah/aaios/issues)
- **Discussions:** [GitHub Discussions](https://github.com/rachidSabah/aaios/discussions)

## Upgrade Path

- From v5.3.0: drop-in upgrade, no migration required
- From v5.2.x: follow [MIGRATION_v5.3.md](MIGRATION_v5.3.md)
- From v5.1.x: upgrade to v5.2.x first, then to v5.3.1-LTS

## Supported Versions

| Version | Status | Support End |
|---------|--------|-------------|
| 5.3.1-LTS | ✅ Active LTS | 2028-07-16 |
| 5.3.0 | ⚠️ Maintenance | 2026-10-16 |
| 5.2.x | ⚠️ Maintenance | 2026-07-16 |
| 5.1.x | ❌ End of life | 2026-04-16 |
| 5.0.x | ❌ End of life | 2026-01-16 |
| 4.1.x | ❌ End of life | 2025-10-16 |

## Deprecation Policy

- Deprecations are announced in a minor release
- Deprecated APIs remain functional for at least 12 months
- Removal happens in the next major version (v6.0)
- Deprecated APIs are documented in [CHANGELOG.md](CHANGELOG.md)

## Contact

- **Issues:** https://github.com/rachidSabah/aaios/issues
- **Discussions:** https://github.com/rachidSabah/aaios/discussions
- **Security:** see [SECURITY.md](SECURITY.md)
