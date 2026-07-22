# AAiOS Release Validation Guide

This document describes the validation protocols, criteria, and deployment gates used to verify AAiOS release builds prior to promoting them to staging or production environments.

---

## 1. Validation Checks and Controls

The `aaios validate` command runs a multi-layered verification suite that audits the system state across the following dimensions:

### Static Code Analysis
Checks python syntax, type safety, and formatting:
*   **Linter**: Runs `ruff check` on the codebase to ensure compliance with styling, unused imports, and syntax deprecations.
*   **Type Checker**: Runs `mypy` to verify strict typing.

### Runtime Integration
Verifies kernel initialization and basic execution:
*   Imports core services and validates DI containers.
*   Tests the asynchronous event bus by publishing test messages and validating subscriber loops.

### Dependency Audit
Verifies that all required packages are present in the active python virtual environment and node_modules directory. Compares imports to `pyproject.toml` and `package.json`.

### Provider Configuration
Checks model provider configurations:
*   Validates that the required LLM API keys are present in environment variables or configuration files.
*   Verifies connection latency to configured providers (e.g. OpenAI, Anthropic, Gemini, Qdrant).

### Database Health
Verifies database integrity:
*   Runs SQLite integrity checks on all `.db` files under `database/`.
*   Checks that migrations are fully applied and schema matches the expectations of the active version.

### Performance Latency
Measures host capability by performing a 1 MB random-byte write disk test. If disk latency exceeds **500 ms**, a performance warning is issued.

---

## 2. Deployment Readiness Score

The Release Validator calculates a deployment readiness score out of 100:

*   **Initial Score**: 100
*   **Database integrity failure**: -30 points (Blocker)
*   **Missing dependency packages**: -25 points (Blocker)
*   **Loose security/directory permissions**: -20 points (Blocker)
*   **API server offline**: -10 points (Recommendation)
*   **Disk latency warning**: -5 points (Recommendation)

### Release Promotion Gates
*   **Staging Release Gate**: Readiness score >= 80/100, zero blockers.
*   **Production Release Gate**: Readiness score >= 90/100, status must read `CERTIFIED` in the validation report.
