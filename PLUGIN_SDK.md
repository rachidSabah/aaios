# AAiOS Plugin SDK Guide
## Version 5.3.2 — Core Extension SDK

This guide describes how to develop custom model providers, agents, tools, and vector adapters.

---

### 1. Model Provider Extension
Implement the `ModelProvider` interface in `services/model_router/providers/base.py`. Register your provider inside the registry to expose it to the central router.

### 2. Creating custom Tools
Expose custom function tools by writing python schemas matching JSON-Schema specifications, making them discoverable by the MCP manager.
