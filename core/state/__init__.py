"""State Manager — event-sourced state for all aggregates.

Current state is a pure fold over the event log. State is partitioned by
aggregate root (Task, Agent, Workflow, MemoryScope, Plugin, User,
ApprovalGate). Each aggregate has a reducer that takes
``(current_state, event) -> new_state``.

This gives us:
  - free replay — any past state is reconstructable by replaying the log
  - free audit — the log IS the audit trail
  - free time-travel debugging — dashboard can scrub through task history
  - trivial disaster recovery — replay the log from a snapshot + WAL

Snapshots are taken every N events per aggregate to bound replay cost.
"""

from __future__ import annotations

from core.state.manager import (
    Aggregate,
    AggregateId,
    Reducer,
    Snapshot,
    StateManager,
    get_state_manager,
    init_state_manager,
    set_state_manager,
)
from core.state.reducers import default_reducer

__all__ = [
    "Aggregate",
    "AggregateId",
    "Reducer",
    "Snapshot",
    "StateManager",
    "default_reducer",
    "get_state_manager",
    "init_state_manager",
    "set_state_manager",
]
