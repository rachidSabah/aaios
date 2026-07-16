# AAiOS v4.1.0 — Migration Guide

## From v4.0 to v4.1

**No breaking changes.** v4.1 is a strict superset of v4.0.

### What Changed
- All stub execution handlers replaced with real implementations
- Audit log is now persistent (SQLite) — survives reboot
- Approval engine supports blocking mode with `await_decision()`
- Execution dashboard page added at `/execution`

### What You Need to Do
1. `git pull && pip install -e .`
2. Optional: Install optional dependencies for execution domains you use:
   ```bash
   pip install playwright openpyxl python-docx reportlab boto3 pyautogui
   playwright install chromium
   ```
3. No config changes needed

## From v3.x to v4.1

### New Subsystem: Execution Platform
v4.0+ adds `services/execution/` — a secure autonomous execution platform with 16 domains. If you don't use it, no action needed. If you do:
- Configure execution policies in your mission WBS nodes
- Set up approval flows for sensitive operations
- Install optional dependencies per domain

## From v2.x to v4.1

### New: Mission System (v3.0)
- `services/organization/` adds mission management above the supervisor
- No changes to existing code needed
- Missions are optional — existing task workflows continue unchanged

### New: Intelligence Engine (v3.1)
- `services/intelligence/` adds self-analysis, forecasting, and optimization
- No configuration needed — runs automatically
- Access via `/intelligence` dashboard page or `aaios intelligence` CLI

## From v1.x to v4.1

See `docs/migration-v2.md` for v1→v2 migration. v2→v4 is fully backward-compatible.
