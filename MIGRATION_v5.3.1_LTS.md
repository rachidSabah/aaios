# AAiOS v5.3.1 LTS — Migration Notes

**From:** v5.3.0 → v5.3.1-LTS
**Date:** 2026-07-16
**Type:** Patch release (no migration required)

---

## Overview

AAiOS v5.3.1-LTS is a **purely additive** patch release. No public APIs
were changed. No data formats were modified. No migration is required.

---

## What Changed

### Code Quality Fixes
- 62 pre-existing mypy errors fixed in `surfaces/api/app.py` and
  `surfaces/cli/__main__.py` (added `cast()` annotations)
- `_api_get()` now accepts an optional `params` keyword argument
- Bare `except Exception` blocks replaced with specific `httpx.HTTPError`

### New LTS Tooling
- `scripts/lts/audit.py` — repository audit
- `scripts/lts/benchmark.py` — performance benchmarks
- `scripts/lts/security.py` — security certification
- `scripts/lts/coverage.py` — coverage aggregator
- `scripts/lts/docs.py` — documentation audit

### Updated Documentation
- `SUPPORT.md` — full LTS policy with supported version matrix

---

## Compatibility

- ✅ All v5.3.0 APIs work unchanged
- ✅ All v5.3.0 CLI commands work unchanged
- ✅ All v5.3.0 dashboard pages work unchanged
- ✅ All v5.3.0 data formats work unchanged
- ✅ All v5.3.0 config files work unchanged

---

## Upgrade Procedure

### Option 1: pip

```bash
pip install --upgrade aaios==5.3.1
```

### Option 2: From source

```bash
git pull
git checkout v5.3.1-LTS
pip install -e .
```

### Verification

```bash
aaios version          # should print 5.3.1
aaios doctor           # health check
aaios research overview    # research platform
aaios engineering overview # engineering platform
```

---

## Rollback

If v5.3.1-LTS causes issues, roll back to v5.3.0:

```bash
pip install aaios==5.3.0
```

No data migration is required in either direction.

---

## Frequently Asked Questions

**Q: Is v5.3.1-LTS a feature release?**
A: No. It's a production-hardening release focused on stability and
certification. No new features were added.

**Q: Should I upgrade from v5.3.0?**
A: Yes. v5.3.1-LTS includes code quality fixes and is the recommended
production release. The upgrade is drop-in.

**Q: How long will v5.3.1-LTS be supported?**
A: 12 months of full support + 12 months of extended security support
(24 months total). See [SUPPORT.md](SUPPORT.md).

**Q: Will there be a v5.3.2?**
A: Yes — v5.3.2 will be the next patch release addressing the known issues
(CORS, rate limiting) identified during LTS certification.

---

## Support

- Issues: https://github.com/rachidSabah/aaios/issues
- Discussions: https://github.com/rachidSabah/aaios/discussions
- Security: see [SECURITY.md](SECURITY.md)
