# AAiOS API and CLI Documentation

This document provides a comprehensive reference for the command-line interface (CLI) and REST API endpoints exposed by the Agentic AI Operating System (AAiOS), with a focus on enterprise validation, self-healing, backups, updating, and continuous monitoring.

---

## 1. Command-Line Interface (CLI) Reference

The CLI is invoked via the main executable wrapper `aaios` or using the python module command `python -m surfaces.cli`.

### `aaios doctor`
Runs health checks against the local installation and performs automatic self-healing repairs.

**Syntax:**
```bash
aaios doctor [OPTIONS]
```

**Options:**
*   `-s, --scan TEXT`: Specifies the scan type.
    *   *Values:* `quick` (default), `full`, `offline`, `online`, `security`, `dependency`, `performance`, `memory`, `storage`, `provider`, `agent`, `plugin`, `mcp`, `database`, `dashboard`, `api`, `cli`, `mission`, `workflow`, `graph`, `vector`, `config`, `audit`, `network`, `windows`.
*   `-h, --heal`: Auto-repair any repairable issues detected during the scan.
*   `-y, --yes`: Auto-approve all repairs (non-interactive mode).

**Examples:**
```bash
# Run a quick check
aaios doctor --scan quick

# Run a full security audit and automatically fix open permissions
aaios doctor --scan security --heal --yes
```

---

### `aaios validate`
Executes release validation checks to ensure readiness for staging or production. Generates a validation report, an enterprise certification card, and a readiness report.

**Syntax:**
```bash
aaios validate
```

**Report Outputs:**
1.  **Validation Report**: Status of static analysis, database integrity, dependencies, plugins, and write-speed latencies.
2.  **Certification Report**: Summary of compliant controls and compliance status.
3.  **Deployment Readiness Report**: A score from 0-100 indicating deployment viability.

---

### `aaios update`
Checks, downloads, and applies upgrades to the AAiOS kernel and configurations.

**Syntax:**
```bash
aaios update [OPTIONS]
```

**Options:**
*   `--channel TEXT`: Release channel to query.
    *   *Values:* `stable` (default), `lts`, `beta`, `nightly`, `enterprise`.
*   `-c, --check`: Query update server and print release notes without downloading or installing.
*   `--pin TEXT`: Pin the system to a specific version (prevents automatic updates).
*   `--offline PATH`: Apply a local update package zip file instead of downloading.

---

### `aaios backup`
Typer command group managing system backups and snapshots.

#### `aaios backup create`
Creates a compressed archive of configurations, databases, and logs.
```bash
aaios backup create [--type Type] [--format Format] [--encrypt] [--tag Tag]
```
*   `--type`: `full` (default), `incremental`, `differential`.
*   `--format`: `zip` (default), `tar`, `json`, `yaml`.
*   `-e, --encrypt`: Encrypts the archive using symmetric Fernet keys.

#### `aaios backup list`
Lists all available backup archives, timestamps, and sizes.
```bash
aaios backup list
```

#### `aaios backup restore`
Restores the workspace state from an archive, running pre-restore checkpoints and automatic rollbacks on validation failures.
```bash
aaios backup restore <BACKUP_ID> [--components Config,Database]
```

#### `aaios backup snapshot-create`
Generates an immutable snapshot containing git versioning and environment configurations.
```bash
aaios backup snapshot-create [--tag tag-name]
```

#### `aaios backup snapshot-list`
Lists all available immutable snapshots.
```bash
aaios backup snapshot-list
```

#### `aaios backup snapshot-compare`
Diffs files between two snapshots, listing added, deleted, and modified paths.
```bash
aaios backup snapshot-compare <SNAP_A_ID> <SNAP_B_ID>
```

---

### `aaios monitor`
Starts a continuous resource telemetry and health check loop.

**Syntax:**
```bash
aaios monitor [--interval Seconds] [--slack Webhook_URL] [--discord Webhook_URL]
```

**Options:**
*   `-i, --interval`: Check loop delay in seconds (default: 5).
*   `--slack`: Webhook URL for Slack alerts.
*   `--discord`: Webhook URL for Discord alerts.

---

## 2. API Endpoints

The API server runs by default on `http://127.0.0.1:8000` when started via `aaios start` or `tasks.ps1 dev`.

### System Health
*   **`GET /healthz`**
    *   *Description:* High-speed load-balancer healthcheck. Returns status code 200 if online.

### Backup and Restore
*   **`GET /api/v1/backups`**
    *   *Description:* Lists all backup metadata.
*   **`POST /api/v1/backups`**
    *   *Description:* Triggers backup creation.
*   **`POST /api/v1/backups/{id}/restore`**
    *   *Description:* Triggers restoration of backup `{id}`.

### Diagnostics and Self-Healing
*   **`GET /api/v1/doctor/scan`**
    *   *Description:* Triggers an active health check.
*   **`POST /api/v1/doctor/heal`**
    *   *Description:* Starts the self-healing routine for detected issues.
