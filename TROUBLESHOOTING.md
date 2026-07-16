# AAiOS Troubleshooting Guide
## Version 5.3.2 — Diagnostic Guide

This guide helps resolve common issues encountered during installation and execution.

---

### 1. Common Installation Issues

#### Issue: PowerShell terminates script execution due to Node warnings
*   **Resolution**: Set `$env:NODE_OPTIONS = '--no-deprecation'` before running installation scripts.

#### Issue: SQLite Database Lock Errors
*   **Resolution**: Run `aaios doctor` to run diagnostic scans and repair corrupted SQLite databases.
