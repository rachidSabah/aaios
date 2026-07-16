# AAiOS Daily Operations Manual
## Version 5.3.2 — Administrator Guide

This guide details the daily operational commands, health tracking checks, and monitoring activities.

---

### 1. Monitoring System Health

To inspect the current status and metrics of active subsystems:
```bash
aaios doctor
```

To run a continuous health monitor checking CPU, memory, and database latencies:
```bash
aaios monitor
```

### 2. Standard Service Logs
Log files are written to the `logs/` directory:
*   `logs/aaios.log`: General kernel execution, model router requests, and system alerts.
*   `logs/audit.log.jsonl`: Security audit records.
