# AAiOS Agent SDK Guide
## Version 5.3.2 — Agent Extension SDK

This guide provides instructions for building custom agents compatible with the Generic Agent Runtime.

---

### 1. GenericAgent Interface

All custom agents must inherit from the `GenericAgent` base class and implement the 11 lifecycle methods:
*   `initialize`
*   `shutdown`
*   `discover_capabilities`
*   `execute_task`
*   `stream_progress`
*   `cancel_task`
*   `report_health`
*   `report_metrics`
*   `request_permission`
*   `serialize_state`
*   `restore_state`
