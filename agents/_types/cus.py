"""CustomAgent — anything plugin-provided."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from agents._types.gen import GenericAgent


@runtime_checkable
class CustomAgent(GenericAgent, Protocol):
    """The Custom agent type.

    A plugin can register an agent that implements ``GenericAgent`` and
    advertises any capability namespace not in the reserved list used by
    the other 15 types. The Supervisor treats it identically to built-in
    agents.

    Reserved capability namespaces (cannot be used by CustomAgent):
      ``supervise.*``, ``plan.*``, ``code.*``, ``desktop.*``, ``web.*``,
      ``browser.*``, ``memory.*``, ``reflect.*``, ``qa.*``, ``security.*``,
      ``deploy.*``, ``vision.*``, ``voice.*``, ``doc.*``, ``workflow.*``.

    Custom agents should use ``custom.<namespace>.*`` (e.g.
    ``custom.slack.send_message``).
    """

    # No additional methods — Custom agents are pure GenericAgent implementations.
    # The differentiation is in the capability manifest (custom.* namespaces).
