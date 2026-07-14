"""Agent Registry exceptions."""

from __future__ import annotations


class AgentRegistryError(RuntimeError):
    """Base class for Agent Registry errors."""


class AgentNotFoundError(AgentRegistryError):
    """Raised when an agent ID is not in the registry."""

    def __init__(self, agent_id: str) -> None:
        super().__init__(f"Agent '{agent_id}' not found in registry.")
        self.agent_id = agent_id


class AgentAlreadyRegisteredError(AgentRegistryError):
    """Raised when an agent ID is already registered."""

    def __init__(self, agent_id: str) -> None:
        super().__init__(
            f"Agent '{agent_id}' is already registered. Unregister first or use a different ID.",
        )
        self.agent_id = agent_id


class AgentInitError(AgentRegistryError):
    """Raised when an agent fails to initialize."""

    def __init__(self, agent_id: str, reason: str) -> None:
        super().__init__(f"Agent '{agent_id}' failed to initialize: {reason}")
        self.agent_id = agent_id
        self.reason = reason


class CircularDependencyError(AgentRegistryError):
    """Raised when agent dependencies form a cycle."""

    def __init__(self, cycle: list[str]) -> None:
        super().__init__(f"Circular dependency detected: {' -> '.join(cycle)}")
        self.cycle = cycle
