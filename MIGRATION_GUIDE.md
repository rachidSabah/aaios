# AAiOS Migration & Upgrade Guide
## Version 5.3.2 — Migration Guide

This guide documents changes and migrations for upgrading to AAiOS v5.3.2.

---

### 1. Upgrading from v5.3.1_LTS

1.  **Backup Workspace**:
    ```powershell
    aaios backup create --type full --tag pre-upgrade-5.3.2
    ```
2.  **Pull Updates**:
    ```powershell
    aaios update
    ```
3.  **Certify System**:
    ```powershell
    aaios certify
    ```
