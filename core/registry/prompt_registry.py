"""Prompt Registry — versioned, templated prompts (Jinja2).

The Supervisor and agents never construct prompts by string concatenation —
they always go through the Prompt Registry. This makes prompts diffable,
reviewable, and A/B-testable.
"""

from __future__ import annotations

from typing import Any

from jinja2 import Environment, StrictUndefined, TemplateError
from pydantic import BaseModel, ConfigDict, Field

from core.logging import get_logger

_log = get_logger(__name__)

# Single Jinja2 environment — strict undefined (no silent fallback to '')
# autoescape=False is intentional: prompts go to LLMs, not browsers — escaping
# would corrupt the prompt content. The prompt inputs are sanitized at the
# gateway layer before reaching this registry.
_ENV = Environment(
    undefined=StrictUndefined,
    autoescape=False,  # nosec B701 — intentional, see comment above
    keep_trailing_newline=True,
)


class PromptError(RuntimeError):
    """Base class for prompt errors."""


class PromptNotFoundError(PromptError):
    """Raised when a prompt is not in the registry."""

    def __init__(self, name: str, version: str | None = None) -> None:
        super().__init__(
            f"Prompt '{name}' version '{version or 'latest'}' not found in registry.",
        )
        self.name = name
        self.version = version


class PromptRenderError(PromptError):
    """Raised when template rendering fails (missing variable, syntax error)."""


class Prompt(BaseModel):
    """A versioned, templated prompt."""

    model_config = ConfigDict(frozen=True)

    name: str = Field(description="Dot-separated, e.g. ``rag.answer``.")
    version: str = Field(default="1.0.0", description="Semver.")
    template: str = Field(description="Jinja2 template body.")
    inputs: list[str] = Field(
        default_factory=list,
        description="Required input variable names.",
    )
    outputs: list[str] = Field(
        default_factory=list,
        description="Allowed output formats (text, json, etc.).",
    )
    description: str = Field(default="")

    def render(self, **kwargs: Any) -> str:
        """Render the prompt with the given inputs.

        Raises PromptRenderError if any required input is missing or the
        template has a syntax error.
        """
        missing = [v for v in self.inputs if v not in kwargs]
        if missing:
            raise PromptRenderError(
                f"Prompt '{self.name}' v{self.version} missing inputs: {missing}",
            )
        try:
            template = _ENV.from_string(self.template)
            return template.render(**kwargs)
        except TemplateError as e:
            raise PromptRenderError(
                f"Prompt '{self.name}' v{self.version} render error: {e}",
            ) from e


class PromptRegistry:
    """The Prompt Registry — versioned, templated prompts."""

    def __init__(self) -> None:
        # name → version → Prompt
        self._prompts: dict[str, dict[str, Prompt]] = {}

    def register(self, prompt: Prompt) -> None:
        """Register a prompt. Overwrites an existing prompt with the same name+version."""
        if prompt.name not in self._prompts:
            self._prompts[prompt.name] = {}
        self._prompts[prompt.name][prompt.version] = prompt
        _log.info("prompt.registered", name=prompt.name, version=prompt.version)

    def unregister(self, name: str, version: str | None = None) -> int:
        """Unregister a prompt. If version is None, unregister all versions.

        Returns the count of removed prompts.
        """
        if name not in self._prompts:
            return 0
        if version is None:
            count = len(self._prompts[name])
            del self._prompts[name]
            _log.info("prompt.unregistered", name=name, count=count)
            return count
        if version not in self._prompts[name]:
            return 0
        del self._prompts[name][version]
        if not self._prompts[name]:
            del self._prompts[name]
        _log.info("prompt.unregistered", name=name, version=version)
        return 1

    def get(self, name: str, version: str | None = None) -> Prompt:
        """Return the prompt with ``name`` (and optionally ``version``).

        If ``version`` is None, returns the highest semver.
        Raises PromptNotFoundError if not found.
        """
        if name not in self._prompts or not self._prompts[name]:
            raise PromptNotFoundError(name, version)
        if version is None:
            # Return the highest semver
            versions = sorted(
                self._prompts[name].keys(),
                key=_semver_key,
                reverse=True,
            )
            return self._prompts[name][versions[0]]
        if version not in self._prompts[name]:
            raise PromptNotFoundError(name, version)
        return self._prompts[name][version]

    def list(self, prefix: str | None = None) -> list[Prompt]:
        """Return all prompts (optionally filtered by name prefix)."""
        result: list[Prompt] = []
        for name, versions in self._prompts.items():
            if prefix is None or name.startswith(prefix):
                result.extend(versions.values())
        return result

    def render(self, prompt_name: str, version: str | None = None, **inputs: Any) -> str:
        """Render a prompt by name (and optionally version)."""
        prompt = self.get(prompt_name, version)
        return prompt.render(**inputs)

    def has(self, name: str, version: str | None = None) -> bool:
        """Return True if the prompt exists."""
        try:
            self.get(name, version)
            return True
        except PromptNotFoundError:
            return False


def _semver_key(version: str) -> tuple[int, int, int]:
    """Parse a semver string into a sortable tuple. Defaults to (0,0,0) on error."""
    parts = version.split(".")
    try:
        major = int(parts[0]) if len(parts) > 0 else 0
        minor = int(parts[1]) if len(parts) > 1 else 0
        patch = int(parts[2]) if len(parts) > 2 else 0
        return (major, minor, patch)
    except ValueError:
        return (0, 0, 0)


# Singleton
_INSTANCE: PromptRegistry | None = None


def get_prompt_registry() -> PromptRegistry:
    """Return the singleton Prompt Registry."""
    global _INSTANCE
    if _INSTANCE is None:
        _INSTANCE = PromptRegistry()
    return _INSTANCE


def set_prompt_registry(registry: PromptRegistry) -> None:
    """Set the singleton Prompt Registry (for testing)."""
    global _INSTANCE
    _INSTANCE = registry
