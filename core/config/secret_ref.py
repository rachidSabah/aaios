"""Secret reference — a typed placeholder for secrets in config values.

Config files never contain secret values. They contain ``${secret:name}``
placeholders. The Config Manager parses these into ``SecretRef`` instances
at load time. Resolution (materializing the actual secret value) happens
in the Security Layer (services/security/) — the kernel never decrypts
secrets.

Example:
    # config.yaml:
    providers:
      openai:
        api_key: ${secret:openai/api_key}

    # Parsed config:
    >>> config.get('providers.openai.api_key')
    SecretRef(name='openai/api_key')
"""

from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel, Field

# Match ${secret:name} — name is any non-} character
_SECRET_REF_PATTERN = re.compile(r"^\$\{secret:([^}]+)\}$")


class SecretRef(BaseModel):
    """A reference to a secret stored in the Security Layer's Secret Store."""

    name: str = Field(description="The secret name, e.g. ``openai/api_key``.")

    def __str__(self) -> str:
        """Render back to the placeholder form."""
        return f"${{secret:{self.name}}}"

    @classmethod
    def parse(cls, value: Any) -> SecretRef | None:
        """Return a SecretRef if ``value`` matches ``${secret:name}``, else None."""
        if not isinstance(value, str):
            return None
        match = _SECRET_REF_PATTERN.match(value.strip())
        if match is None:
            return None
        return cls(name=match.group(1))

    @classmethod
    def is_secret_ref(cls, value: Any) -> bool:
        """Return True if ``value`` is a ``${secret:...}`` placeholder."""
        return cls.parse(value) is not None
