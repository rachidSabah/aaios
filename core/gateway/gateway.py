"""Gateway facade — the single entry point for all I/O.

Components obtain the Gateway via ``get_gateway()`` and call its sub-gateways:

    gateway = get_gateway()
    data = await gateway.fs.read(path, actor=actor, sandbox_root=root)
    result = await gateway.shell.exec('echo hello', actor=actor)
    response = await gateway.net.request('GET', url, actor=actor)

The Gateway is the ONLY place in the codebase that performs I/O. CI
enforces this (INV-02).
"""

from __future__ import annotations

from dataclasses import dataclass

from core.gateway.fs import FileSystemGateway, get_fs_gateway
from core.gateway.net import NetworkGateway, get_net_gateway
from core.gateway.shell import ShellGateway, get_shell_gateway


@dataclass
class Gateway:
    """The unified Gateway facade."""

    fs: FileSystemGateway
    shell: ShellGateway
    net: NetworkGateway

    @classmethod
    def default(cls) -> Gateway:
        """Return a Gateway wired with the default singleton sub-gateways."""
        return cls(
            fs=get_fs_gateway(),
            shell=get_shell_gateway(),
            net=get_net_gateway(),
        )


_INSTANCE: Gateway | None = None


def get_gateway() -> Gateway:
    """Return the singleton Gateway."""
    global _INSTANCE
    if _INSTANCE is None:
        _INSTANCE = Gateway.default()
    return _INSTANCE
