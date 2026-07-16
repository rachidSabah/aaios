# AAiOS MCP Integration Guide
## Version 5.3.2 — Model Context Protocol

This document details integration with Model Context Protocol (MCP) servers.

---

### 1. Registering an MCP Server

Register servers in `config/config.yaml`:
```yaml
mcp:
  servers:
    filesystem:
      command: npx
      args: ["-y", "@modelcontextprotocol/server-filesystem", "E:\AAIOS"]
```

### 2. Hot-Reloading MCP Servers
The MCP manager monitors modifications and hot-reloads servers dynamically.
