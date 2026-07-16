# AAiOS Backup System Guide
## Version 5.3.2 — Backup Operations

This document describes how to execute workspace backups, encrypt archives, and manage backup storage.

---

### 1. Creating a Backup

To create a full workspace backup archive (encrypted by default):
```bash
aaios backup create --type full --tag my-tag
```

### 2. Supported Backup Types

*   **Full Backup**: Copies all configuration files, database schemas, and source directories.
*   **Incremental Backup**: Copies files modified since the last backup.
*   **Differential Backup**: Copies files modified since the last full backup.
