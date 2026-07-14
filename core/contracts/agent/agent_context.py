"""Agent context — passed to ``initialize()`` and ``execute_task()``.

The context carries:
  - The agent's environment (paths, sandbox root, env vars, config)
  - The SecretResolver (returns SecretRef → plaintext, never logged)
  - The event bus (so agents can emit events without importing the singleton)
  - The gateway (the only path to I/O — INV-02)
  - The logger (correlation-aware)
  - The task correlation ID (for context binding)

The context is constructed by the Agent Registry at registration time and
passed to ``initialize()``. For ``execute_task()``, a per-task context is
derived (same env, but with the task's correlation_id bound).
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

if TYPE_CHECKING:
    from core.config import SecretRef


class SecretResolver(Protocol):
    """The interface for resolving SecretRef placeholders to plaintext.

    Implemented by the Security Layer (services/security/, Phase 8). Agents
    obtain plaintext secrets ONLY through this interface — never via direct
    file reads or env vars.

    The returned plaintext is the caller's responsibility: don't log it,
    don't persist it, clear it from memory when done.
    """

    async def resolve(self, ref: str | SecretRef) -> str:
        """Return the plaintext secret for ``ref``.

        Args:
            ref: either a SecretRef object or the secret name string.

        Raises:
            SecretNotFoundError: if the secret is not in the store.
            SecretStoreLockedError: if the master key is unavailable.
        """
        ...


class AgentEnvironment(BaseModel):
    """The environment an agent runs in.

    Captured at boot from the platform adapter + config manager. Agents
    use this for path resolution, sandboxing, and shell selection.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True, frozen=False)

    home_dir: Path
    config_dir: Path
    data_dir: Path
    log_dir: Path
    temp_dir: Path
    sandbox_root: Path | None = Field(
        default=None, description="Project-scoped sandbox for filesystem access."
    )
    env_vars: dict[str, str] = Field(default_factory=dict)
    default_shell: str = Field(default="bash", description="PowerShell or bash.")
    python_path: str | None = Field(
        default=None, description="Path to the Python interpreter the agent may use."
    )


class AgentContext(BaseModel):
    """The context passed to ``initialize()`` and ``execute_task()``.

    The ``bus``, ``gateway``, ``config``, ``secret_resolver``, and ``logger``
    are runtime singletons (not Pydantic-serializable); they're carried as
    ``Any`` to keep the model happy. They are always set by the Agent
    Registry before being passed to an agent.

    The ``task_correlation_id`` is None at ``initialize()`` time and set
    to the task's UUID at ``execute_task()`` time.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    environment: AgentEnvironment
    bus: Any = Field(default=None, description="EventBus singleton (set by registry).")
    gateway: Any = Field(default=None, description="Gateway facade (set by registry).")
    config: Any = Field(default=None, description="ConfigManager singleton (set by registry).")
    secret_resolver: Any = Field(default=None, description="SecretResolver (set by registry).")
    logger: Any = Field(default=None, description="structlog logger (set by registry).")
    task_correlation_id: UUID | None = Field(default=None, description="Set per-task.")
    metadata: dict[str, Any] = Field(default_factory=dict)

    def derive_for_task(self, task_correlation_id: UUID) -> AgentContext:
        """Return a copy of this context bound to a specific task."""
        return self.model_copy(update={"task_correlation_id": task_correlation_id})
