# AAiOS Release and Update Management Guide
## Version 5.3.2 — Enterprise Release Guide

This document describes versioning schemes, release cycles, delta updates, and version pinning configurations for AAiOS.

---

### 1. Release Versioning Scheme

AAiOS follows Semantic Versioning (SemVer) principles:
*   **Major Version**: Represents architectural transitions or breaking changes.
*   **Minor Version**: Represents new features and service additions.
*   **Patch Version**: Represents backward-compatible security enhancements and fixes.

### 2. Update Channels

The platform uses five distribution channels:
1.  **LTS (Long-Term Support)**: Checked stability. Security updates only.
2.  **Stable**: Default release channel. Includes minor updates.
3.  **Beta**: Pre-releases for developer verification and staging environments.
4.  **Nightly**: Active master branch builds for daily integration checks.
5.  **Enterprise**: High-governance, audited LTS packages.

---

### 3. Delta Updates & Migration Flow

When an update is applied:
1.  **Release Check**: The platform queries `aaios update check` to retrieve the latest version from the selected channel.
2.  **Backup Point**: A full snapshot is generated before applying any delta changes.
3.  **Package Installation**: Changed files are extracted and copied into place.
4.  **Database Migration**: The migration engine executes SQL scripts to patch schemas.
5.  **Validation Check**: The validator verifies system health. If checks fail, an automated rollback is initiated to restore the pre-update state.

---

### 4. Version Pinning Configuration

You can pin specific versions in `config/config.yaml`:
```yaml
update:
  channel: stable
  pinned_version: "5.3.2"
  auto_update: false
  allow_rollback: true
```
This configuration blocks automatic update updates and holds the codebase strictly at the pinned release.
