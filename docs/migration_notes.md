# AAiOS Migration & Upgrade Notes
## Version 5.3.2 — Enterprise Migration Reference

This document outlines key migrations, configuration updates, database schema changes, and rollback instructions for upgrading to AAiOS v5.3.2.

---

### 1. Database Schema Migrations

#### A. Mission Database (`mission.db`)
*   Added `schema_migrations` tracking table to register schema hashes.
*   Added `priority` column to `missions` table to improve WBS sequencing.

#### B. Workflow Database (`workflow.db`)
*   Added `workflow_runs` table tracking execution parameters, status, and completion times.

---

### 2. Configuration Key Updates

The following keys have been introduced to `config/config.yaml`:
```yaml
update:
  channel: stable           # lts, stable, beta, nightly
  pinned_version: "5.3.2"   # lock version updates
  auto_update: false        # disable automatic upgrades

monitoring:
  alert_channels:           # configure alert targets
    - slack
    - discord
    - console
  cpu_threshold_pct: 85.0
  ram_threshold_pct: 90.0
```

---

### 3. Step-by-Step Migration Guide

1.  **Backup Existing State**: Generate a snapshot of the current workspace before migrating:
    ```powershell
    aaios backup create --type full --tag pre-migration-v5.3.2
    ```
2.  **Download Release Package**: Pull the v5.3.2 update bundle:
    ```powershell
    aaios update download --version 5.3.2
    ```
3.  **Apply Migration**: Apply version file deltas and update database schemas:
    ```powershell
    aaios update apply --version 5.3.2
    ```
4.  **Certify System**: Validate the upgraded system state:
    ```powershell
    aaios certify
    ```

### 4. Upgrade Rollback Execution

If the certification validation step fails or flags compatibility issues, rollback immediately to restore the pre-migration snapshot:
```powershell
aaios backup restore <pre-migration-backup-id>
```
This restores all files and returns database files to their correct pre-update versions.
