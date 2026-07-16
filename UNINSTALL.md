# AAiOS Uninstallation Manual
## Version 5.3.2 — System De-provisioning

This guide provides instructions for uninstalling AAiOS and de-provisioning workspace files.

---

### 1. Automated Uninstallation

Run the following command to start the uninstallation process:
```bash
aaios uninstall
```

### 2. Command Flags

*   `--silent`: Run without interactive confirmations.
*   `--everything`: Purge all configurations, databases, model files, backups, caches, logs, and python virtual environments.
*   `--keep-data`: Preserve user database files while removing application runtimes.
