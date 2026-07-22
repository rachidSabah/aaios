# AAiOS Version Upgrade Guide
## Version 5.3.2 — Upgrade Manual

This guide describes how to upgrade AAiOS to a newer version.

---

### 1. Checking for Updates

To query active distribution channels (LTS/Stable/Beta) for available updates:
```bash
aaios update
```

### 2. Applying an Update

To perform a version delta upgrade:
```bash
aaios update --channel stable
```

The upgrade runner performs the following steps:
1.  Generates a backup snapshot of the workspace.
2.  Applies update file differentials.
3.  Executes database schema migrations.
4.  Certifies system states via `aaios certify`.
5.  If validation checks fail, the upgrade is rolled back automatically.
