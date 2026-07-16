# AAiOS Operations Guide

This guide details day-to-day operations, monitoring configurations, and diagnostic processes for maintaining a production-grade Agentic AI Operating System (AAIOS) environment.

---

## 1. Directory Structure and Workspace Layout

The AAIOS workspace is structured in the following directories, located under the workspace root:

```text
workspace_root/
├── config/             # YAML configurations, defaults, and API keys
├── database/           # SQLite database files for all runtime subsystems
├── backups/            # Compressed backup zip archives
├── snapshots/          # Version-controlled environment snapshots
├── logs/               # Telemetry and debugging log files
├── secrets/            # Encrypted credentials and Fernet symmetric keys
├── certificates/       # Self-signed SSL certificates for node endpoints
├── downloads/          # Downloaded update packages and delta archives
├── caches/             # Model response and vector storage caches
├── runtime/            # Runtime PID files and socket bindings
└── tmp/                # Short-term files and scratch data
```

---

## 2. Telemetry and Continuous Monitoring

AAIOS ships with a `ContinuousHealthMonitor` that tracks system resources and API availability. 

### Core SLA Thresholds
Alerts are generated when the following thresholds are breached:
*   **CPU Usage**: Warning at 80%, Critical/Degradation at 90%.
*   **RAM Consumption**: Warning at 90%, Critical at 95%.
*   **Disk Capacity**: Critical alert when free space drops below 2.0 GB.
*   **API Latency**: Warning when healthcheck endpoints respond in >1.0 second.

### Configuring Alert Channels
To stream alerts to communication channels, configure webhooks using the CLI:
```bash
aaios monitor --slack "https://hooks.slack.com/services/..." --discord "https://discord.com/api/webhooks/..."
```

---

## 3. Logging and Rotation Policy

Logs are written using structured JSON output to `logs/aaios.log`.
*   **Log Level**: Configurable via `config/config.yaml` (`debug`, `info`, `warning`, `error`, `critical`).
*   **Log Rotation**: Log files rotate automatically when they reach 50 MB, retaining up to 10 historical copies.
*   **Structured Format**: Every log contains timestamp, event namespace, severity level, and correlation IDs to support tracing through multi-agent tasks.

---

## 4. Runbook: Investigating System Failure

If a critical alert is dispatched (e.g. `DB_FILE_MISSING` or `SECRETS_DIR_PERMISSIONS_LOOSE`), follow this recovery procedure:

### Step 1: Run Diagnostics
Run a full scan to identify the root cause of the error:
```bash
aaios doctor --scan full
```
Review the health score and the issues table.

### Step 2: Run Self-Healing
If the issue has a repair action available, execute self-healing:
```bash
aaios doctor --scan full --heal --yes
```

### Step 3: Verify Integrity
Verify that all system tests pass:
```bash
aaios validate
```
Ensure the readiness score returns to >80/100 and status reads `CERTIFIED`.
