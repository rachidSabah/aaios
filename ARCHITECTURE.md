# AAiOS Core Architecture
## Version 5.3.2 — Core Layer Specifications

This document outlines the core architectural components of AAiOS.

---

### 1. Decoupled Modular Layers

```
┌──────────────────┐
│ surfaces/cli/    │ ◄── Typer CLI commands
└────────┬─────────┘
         │
┌────────▼─────────┐
│ services/        │ ◄── Diagnostic, Backup, Update, and Reset APIs
└────────┬─────────┘
         │
┌────────▼─────────┐
│ core/            │ ◄── Core bootstrap and configuration bindings
└──────────────────┘
```

### 2. Dependency Invariants

*   Core modules MUST NOT import from surfaces or services.
*   Surface CLI tools communicate with services strictly via standardized API parameters.
