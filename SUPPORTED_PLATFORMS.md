# Supported Operating Systems & Platforms
## Version 5.3.2 — Compatibility Matrix

AAiOS is optimized for Windows 11 environments, with full compatibility support for Linux and WSL2.

### 1. Supported Environments

*   **Windows 11**: Fully supported. Uses PowerShell-first script runners, Windows Job Objects for resource throttling, AppContainer, and WDAC policies.
*   **Linux (Ubuntu 22.04 LTS+)**: Fully supported. Uses standard Bash, systemd service units, and standard process namespaces.
*   **WSL2 (Windows Subsystem for Linux 2)**: Fully supported. Bridges Windows filesystems and Linux runtime libraries.
*   **Docker Containers**: Supported for isolated worker environments.

### 2. Required System Dependencies

| Dependency | Minimum Version | Purpose |
| :--- | :--- | :--- |
| **Python** | `3.12+` (3.14 recommended) | Core runtime execution |
| **Node.js** | `22.0+` | CLI surface and Next.js dashboard |
| **pnpm** | `latest` | Node package management |
| **git** | `latest` | Versioning and repository updates |
