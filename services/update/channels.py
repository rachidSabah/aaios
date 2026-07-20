"""Release channel manager — which channels are enabled and auto-updated.

Channels are opt-in. STABLE is on by default. BETA/NIGHTLY/ENTERPRISE must be
explicitly enabled (they can pull pre-releases / nightly builds). LTS follows
the stable cadence but only adopts ``-lts``-tagged releases. This manager is
the single source of truth the :class:`UpdateManager` consults before
auto-updating, so channel policy is enforced in one place.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from core.logging import get_logger
from services.update.models import ReleaseChannel

_log = get_logger(__name__)


class ChannelPolicy(StrEnum):
    """Auto-update behaviour per channel."""

    AUTO = "auto"          # check + install automatically
    NOTIFY = "notify"      # check + notify, install on user action
    OFF = "off"            # never check


@dataclass
class ChannelState:
    """Per-channel configuration."""

    channel: ReleaseChannel
    policy: ChannelPolicy = ChannelPolicy.OFF
    enabled: bool = False


_DEFAULTS: dict[ReleaseChannel, ChannelState] = {
    ReleaseChannel.STABLE: ChannelState(ReleaseChannel.STABLE, ChannelPolicy.AUTO, True),
    ReleaseChannel.LTS: ChannelState(ReleaseChannel.LTS, ChannelPolicy.AUTO, False),
    ReleaseChannel.BETA: ChannelState(ReleaseChannel.BETA, ChannelPolicy.NOTIFY, False),
    ReleaseChannel.NIGHTLY: ChannelState(ReleaseChannel.NIGHTLY, ChannelPolicy.NOTIFY, False),
    ReleaseChannel.ENTERPRISE: ChannelState(
        ReleaseChannel.ENTERPRISE, ChannelPolicy.OFF, False
    ),
}


class ReleaseChannelManager:
    """Manage enabled channels and their auto-update policies."""

    def __init__(self) -> None:
        self._states: dict[ReleaseChannel, ChannelState] = {
            ch: ChannelState(channel=s.channel, policy=s.policy, enabled=s.enabled)
            for ch, s in _DEFAULTS.items()
        }

    def enable(self, channel: ReleaseChannel, *, policy: ChannelPolicy | None = None) -> None:
        """Enable a channel, optionally overriding its policy."""
        st = self._states[channel]
        st.enabled = True
        if policy is not None:
            st.policy = policy
        _log.info("update.channel.enabled", channel=channel.value, policy=st.policy.value)

    def disable(self, channel: ReleaseChannel) -> None:
        """Disable a channel (it will not be checked)."""
        self._states[channel].enabled = False
        _log.info("update.channel.disabled", channel=channel.value)

    def set_policy(self, channel: ReleaseChannel, policy: ChannelPolicy) -> None:
        """Set the auto-update policy for a channel."""
        self._states[channel].policy = policy

    def is_enabled(self, channel: ReleaseChannel) -> bool:
        """Whether a channel is currently checked."""
        return self._states[channel].enabled

    def policy_for(self, channel: ReleaseChannel) -> ChannelPolicy:
        """The current policy for a channel."""
        return self._states[channel].policy

    def enabled_channels(self) -> list[ReleaseChannel]:
        """Channels that should be checked, in priority order."""
        order = [
            ReleaseChannel.STABLE,
            ReleaseChannel.LTS,
            ReleaseChannel.BETA,
            ReleaseChannel.NIGHTLY,
            ReleaseChannel.ENTERPRISE,
        ]
        return [ch for ch in order if self._states[ch].enabled]

    def as_dict(self) -> dict[str, dict[str, str]]:
        """Serializable snapshot for diagnostics/API responses."""
        return {
            ch.value: {"enabled": str(st.enabled), "policy": st.policy.value}
            for ch, st in self._states.items()
        }
