# Supported AI Agents in AAiOS
## Version 5.3.2 — Generic Agent Runtime

AAiOS abstracts all agent binaries and CLI wrappers behind a unified `GenericAgent` interface.

### 1. Native & Integrated Agents

*   **Claude Code Coding Agent**: Wraps the `@anthropic-ai/claude-code` global CLI. Handles file modifications, terminal command executions, git diff additions, and project audits.
*   **Hermes Desktop Agent**: Python daemon that intercepts workspace file changes, registers automated task runs, and manages system state transitions.
*   **Default Supervisor**: A reflection-based master agent that parses goals, drafts WBS (Work Breakdown Structures), and delegates subtasks.
*   **QAAgent**: Verifies code modifications, checks for Ruff/Mypy errors, and ensures test suites pass successfully.
*   **SecurityAgent**: Runs automated code security audits using tools like Bandit.

*   **9Router Local Proxy**: Connects Claude Code, Hermes, and custom agents to over 40+ LLM providers with automatic 3-tier fallbacks, token-saving compressions, and local dashboards at `http://localhost:20128`.

---

### 2. Third-Party Agent Extensibility
The Generic Agent Registry allows wrapping any third-party agent (e.g. OpenHands, Cline, Roo Code, Gemini CLI, Codex CLI) by providing an implementation of the 11-method lifecycle.
