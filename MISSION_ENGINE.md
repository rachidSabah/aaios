# AAiOS Mission Engine Reference
## Version 5.3.2 — Goal Decomposition & Orchestration

The Mission Engine parses goals, decomposing them into Work Breakdown Structures (WBS) and managing task allocation.

---

### 1. Goal Parsing

When a user submits a goal, the Mission Engine:
1.  Analyzes target constraints.
2.  Decomposes the goal into distinct, dependency-linked WBS nodes.
3.  Stores nodes in `database/mission.db`.

### 2. Task Delegation

WBS nodes are assigned to agents registered in the Agent Registry based on their advertised capabilities.
