# AAiOS Backup Guide

This document details the configuration, administration, and execution of backup routines for securing the databases, memory indexes, and secrets of the Agentic AI Operating System (AAIOS).

---

## 1. Backup Strategies and File Selection

AAIOS supports three backup strategies, which are selected using the `--type` flag during creation:

| Backup Type | Description | File Selection Criteria |
| :--- | :--- | :--- |
| **Full** | Archives the entire workspace state (except binaries). | All files in `config/`, `database/`, `secrets/`, `certificates/`, `plugins/`. |
| **Incremental** | Archives only files modified since the last backup. | Files with `mtime` newer than the latest metadata timestamp. |
| **Differential** | Archives only files modified since the last *full* backup. | Files with `mtime` newer than the latest *full* backup timestamp. |

---

## 2. Cryptographic Encryption and Key Management

To safeguard sensitive API keys and database tables, backup archives can be encrypted using Fernet symmetric encryption.

> [!CAUTION]
> If a Fernet encryption key is lost, any encrypted backup created with it becomes permanently unrecoverable. Store backup keys in a secure hardware security module (HSM) or an external vault.

### Enabling Encryption
To create an encrypted backup:
```bash
aaios backup create --encrypt
```
This reads the encryption key from `secrets/backup_key.key` or generates a new key if it does not exist.

### Key Rotation Procedure
1.  **Backup the current key**: Copy `secrets/backup_key.key` to a secure offline location.
2.  **Generate a new key**: Run a standard Fernet generation command.
3.  **Replace the active key**: Overwrite `secrets/backup_key.key` with the new key.
4.  *Note:* Backups created before rotation must be restored using their respective historical keys.

---

## 3. Metadata Schema and Integrity Checks

Every backup package contains a JSON metadata descriptor (`backup_metadata.json`) containing:
*   **id**: Unique UUID for the backup.
*   **backup_type**: `full`, `incremental`, or `differential`.
*   **timestamp**: ISO-8601 creation time.
*   **git_commit**: Commit hash of the active installation.
*   **database_versions**: Max schema migration IDs for SQLite tables.
*   **checksums**: SHA-256 hashes of all archived files.

During recovery, the system calculates file hashes and compares them to these values to verify that archives have not been corrupted or tampered with.

---

## 4. Scheduling Backups

To automate backups in an enterprise environment, set up a Windows Task Scheduler task or a cron job.

### Example Windows Task Scheduler (PowerShell)
To run a full encrypted backup daily at 2:00 AM:
```powershell
$action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-Command & 'E:\AAIOS\.venv\Scripts\python.exe' -m surfaces.cli backup create --type full --encrypt"
$trigger = New-ScheduledTaskTrigger -Daily -At 2am
Register-ScheduledTask -TaskName "AAIOS_Daily_Backup" -Action $action -Trigger $trigger
```
