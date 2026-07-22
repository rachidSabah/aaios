"""Runtime Discovery — Provider Specifications.

Extensible registry of AI agent specifications. Each spec defines HOW to
detect a specific agent — it is NOT a hardcoded provider instance. The
DiscoveryEngine uses these specs to find real installations on the host.

Specs are data-driven. New agents can be added by appending to
``BUILTIN_SPECS`` or by calling ``ProviderSpecRegistry.register()`` at
runtime. No code changes required to support new agents.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

__all__ = [
    "AgentCategory",
    "DetectionMethod",
    "ProviderSpec",
    "ProviderSpecRegistry",
    "BUILTIN_SPECS",
    "get_spec_registry",
]


class AgentCategory(StrEnum):
    """Category of AI agent."""

    CODING = "coding"
    DESKTOP = "desktop"
    RESEARCH = "research"
    LOCAL_LLM = "local_llm"
    ORCHESTRATION = "orchestration"
    MCP_SERVER = "mcp_server"
    WORKFLOW = "workflow"
    CUSTOM = "custom"


class DetectionMethod(StrEnum):
    """How a provider was detected."""

    PATH = "path"
    FILESYSTEM = "filesystem"
    PACKAGE_MANAGER = "package_manager"
    REGISTRY = "registry"
    PROCESS = "process"
    PORT = "port"
    MCP_CONFIG = "mcp_config"
    ENVIRONMENT = "environment"
    MANUAL = "manual"


@dataclass
class ProviderSpec:
    """Specification for detecting and validating one AI agent.

    This is a RECIPE for discovery, not a discovered provider instance.
    The DiscoveryEngine uses this spec to find real installations.
    """

    spec_id: str = ""
    name: str = ""
    vendor: str = ""
    description: str = ""
    category: AgentCategory = AgentCategory.CUSTOM

    # Binary names to search for (in order of preference)
    binary_names: list[str] = field(default_factory=list)

    # Known install directories (relative to home or absolute)
    install_dirs: list[str] = field(default_factory=list)

    # Package manager packages
    npm_packages: list[str] = field(default_factory=list)
    pip_packages: list[str] = field(default_factory=list)
    cargo_packages: list[str] = field(default_factory=list)
    brew_packages: list[str] = field(default_factory=list)
    apt_packages: list[str] = field(default_factory=list)
    winget_packages: list[str] = field(default_factory=list)
    scoop_packages: list[str] = field(default_factory=list)

    # Version detection
    version_args: list[str] = field(default_factory=lambda: ["--version"])
    version_regex: str = r"(\d+\.\d+(?:\.\d+)?)"

    # Health check
    health_args: list[str] = field(default_factory=lambda: ["--help"])
    health_timeout_s: float = 10.0

    # Capabilities (probed dynamically, these are hints)
    expected_capabilities: list[str] = field(default_factory=list)

    # MCP support
    supports_mcp: bool = False

    # Configuration file locations (relative to home)
    config_files: list[str] = field(default_factory=list)

    # Environment variables that indicate this provider
    env_indicators: list[str] = field(default_factory=list)

    # Icon (emoji or data URI)
    icon: str = ""

    # License
    license: str = ""

    # Website
    website: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "spec_id": self.spec_id,
            "name": self.name,
            "vendor": self.vendor,
            "description": self.description,
            "category": self.category.value,
            "binary_names": list(self.binary_names),
            "install_dirs": list(self.install_dirs),
            "npm_packages": list(self.npm_packages),
            "pip_packages": list(self.pip_packages),
            "cargo_packages": list(self.cargo_packages),
            "brew_packages": list(self.brew_packages),
            "apt_packages": list(self.apt_packages),
            "winget_packages": list(self.winget_packages),
            "scoop_packages": list(self.scoop_packages),
            "version_args": list(self.version_args),
            "version_regex": self.version_regex,
            "health_args": list(self.health_args),
            "health_timeout_s": self.health_timeout_s,
            "expected_capabilities": list(self.expected_capabilities),
            "supports_mcp": self.supports_mcp,
            "config_files": list(self.config_files),
            "env_indicators": list(self.env_indicators),
            "icon": self.icon,
            "license": self.license,
            "website": self.website,
        }


class ProviderSpecRegistry:
    """Registry of provider specifications.

    Specs are detection recipes — not provider instances. The registry
    is extensible: new specs can be registered at runtime.
    """

    def __init__(self) -> None:
        self._specs: dict[str, ProviderSpec] = {}
        for spec in BUILTIN_SPECS:
            self.register(spec)

    def register(self, spec: ProviderSpec) -> None:
        """Register a new provider spec."""
        self._specs[spec.spec_id] = spec

    def get(self, spec_id: str) -> ProviderSpec | None:
        return self._specs.get(spec_id)

    def list_all(self) -> list[ProviderSpec]:
        return list(self._specs.values())

    def list_by_category(self, category: AgentCategory) -> list[ProviderSpec]:
        return [s for s in self._specs.values() if s.category == category]

    def find_by_binary(self, binary_name: str) -> ProviderSpec | None:
        """Find the spec that matches a binary name."""
        for spec in self._specs.values():
            if binary_name in spec.binary_names:
                return spec
        return None

    def to_dict(self) -> dict[str, Any]:
        return {
            "specs": {sid: s.to_dict() for sid, s in self._specs.items()},
            "count": len(self._specs),
        }


# ---------------------------------------------------------------------------
# Built-in specifications — 35+ AI agents
# ---------------------------------------------------------------------------

BUILTIN_SPECS: list[ProviderSpec] = [
    # --- Coding Agents ---
    ProviderSpec(
        spec_id="claude-code",
        name="Claude Code",
        vendor="Anthropic",
        description="Claude Code — AI coding agent by Anthropic",
        category=AgentCategory.CODING,
        binary_names=["claude", "claude-code"],
        npm_packages=["@anthropic-ai/claude-code"],
        install_dirs=[".claude", ".claude-code"],
        expected_capabilities=["coding", "reasoning", "planning", "terminal", "filesystem", "git"],
        supports_mcp=True,
        config_files=[".claude/config.json", ".claude-code/config.json"],
        env_indicators=["ANTHROPIC_API_KEY", "CLAUDE_API_KEY"],
        icon="🤖",
        license="proprietary",
        website="https://anthropic.com/claude-code",
    ),
    ProviderSpec(
        spec_id="hermes",
        name="Hermes",
        vendor="AgentOS",
        description="Hermes — desktop automation agent",
        category=AgentCategory.DESKTOP,
        binary_names=["hermes", "hermes-daemon"],
        npm_packages=["@agentos/hermes"],
        expected_capabilities=[
            "desktop_automation",
            "browser_automation",
            "screenshot",
            "terminal",
        ],
        supports_mcp=True,
        icon="🪽",
        license="MIT",
        website="https://github.com/agentos/hermes",
    ),
    ProviderSpec(
        spec_id="opencode",
        name="OpenCode",
        vendor="Open Source",
        description="OpenCode — open-source coding agent",
        category=AgentCategory.CODING,
        binary_names=["opencode", "open-code"],
        npm_packages=["opencode"],
        expected_capabilities=["coding", "reasoning", "terminal"],
        supports_mcp=True,
        icon="🔓",
        license="MIT",
    ),
    ProviderSpec(
        spec_id="agy-cli",
        name="AGY CLI",
        vendor="AGY Project",
        description="AGY CLI — AI agent CLI",
        category=AgentCategory.CODING,
        binary_names=["agy", "agy-cli"],
        npm_packages=["agy-cli"],
        expected_capabilities=["coding", "reasoning", "terminal"],
        icon="🎯",
        license="MIT",
    ),
    ProviderSpec(
        spec_id="gemini-cli",
        name="Gemini CLI",
        vendor="Google",
        description="Gemini CLI — Google's AI agent CLI",
        category=AgentCategory.CODING,
        binary_names=["gemini", "gemini-cli"],
        npm_packages=["@google/gemini-cli"],
        expected_capabilities=["coding", "reasoning", "vision", "terminal"],
        env_indicators=["GOOGLE_API_KEY", "GEMINI_API_KEY"],
        icon="💎",
        license="proprietary",
        website="https://ai.google.dev",
    ),
    ProviderSpec(
        spec_id="codex-cli",
        name="Codex CLI",
        vendor="OpenAI",
        description="Codex CLI — OpenAI's coding agent",
        category=AgentCategory.CODING,
        binary_names=["codex", "openai-codex"],
        npm_packages=["@openai/codex"],
        expected_capabilities=["coding", "reasoning", "terminal"],
        env_indicators=["OPENAI_API_KEY"],
        icon="🔑",
        license="proprietary",
        website="https://openai.com/codex",
    ),
    ProviderSpec(
        spec_id="cursor-cli",
        name="Cursor CLI",
        vendor="Cursor",
        description="Cursor CLI — AI code editor CLI",
        category=AgentCategory.CODING,
        binary_names=["cursor", "cursor-cli"],
        expected_capabilities=["coding", "reasoning"],
        icon="🖱️",
        license="proprietary",
    ),
    ProviderSpec(
        spec_id="continue",
        name="Continue",
        vendor="Continue Dev",
        description="Continue — open-source AI coding assistant",
        category=AgentCategory.CODING,
        binary_names=["continue", "continue-cli"],
        npm_packages=["continue"],
        pip_packages=["continue-dev"],
        expected_capabilities=["coding", "reasoning", "terminal"],
        supports_mcp=True,
        icon="▶️",
        license="Apache-2.0",
    ),
    ProviderSpec(
        spec_id="goose",
        name="Goose",
        vendor="Block",
        description="Goose — AI agent by Block",
        category=AgentCategory.CODING,
        binary_names=["goose"],
        expected_capabilities=["coding", "reasoning", "terminal"],
        supports_mcp=True,
        icon="🪿",
        license="Apache-2.0",
    ),
    ProviderSpec(
        spec_id="aider",
        name="Aider",
        vendor="Aider",
        description="Aider — AI pair programming in the terminal",
        category=AgentCategory.CODING,
        binary_names=["aider"],
        pip_packages=["aider-chat"],
        expected_capabilities=["coding", "reasoning", "git", "terminal"],
        icon="🤝",
        license="Apache-2.0",
        website="https://aider.chat",
    ),
    ProviderSpec(
        spec_id="open-interpreter",
        name="Open Interpreter",
        vendor="Open Interpreter",
        description="Open Interpreter — code interpreter agent",
        category=AgentCategory.CODING,
        binary_names=["interpreter", "open-interpreter"],
        pip_packages=["open-interpreter"],
        expected_capabilities=["coding", "reasoning", "terminal", "filesystem"],
        icon="🐍",
        license="AGPL-3.0",
    ),
    ProviderSpec(
        spec_id="openhands",
        name="OpenHands",
        vendor="OpenHands",
        description="OpenHands — autonomous coding agent",
        category=AgentCategory.CODING,
        binary_names=["openhands", "openhands-cli"],
        pip_packages=["openhands"],
        expected_capabilities=["coding", "reasoning", "terminal", "docker", "browser"],
        supports_mcp=True,
        icon="👐",
        license="MIT",
    ),
    ProviderSpec(
        spec_id="cline",
        name="Cline",
        vendor="Cline",
        description="Cline — AI coding assistant",
        category=AgentCategory.CODING,
        binary_names=["cline", "cline-cli"],
        npm_packages=["cline"],
        expected_capabilities=["coding", "reasoning", "terminal"],
        icon="📐",
        license="Apache-2.0",
    ),
    ProviderSpec(
        spec_id="roo-code",
        name="Roo Code",
        vendor="Roo Vet",
        description="Roo Code — AI coding assistant",
        category=AgentCategory.CODING,
        binary_names=["roo", "roo-cli", "roo-code"],
        expected_capabilities=["coding", "reasoning", "terminal"],
        icon="🦘",
        license="Apache-2.0",
    ),
    # --- Orchestration Frameworks ---
    ProviderSpec(
        spec_id="crewai",
        name="CrewAI",
        vendor="CrewAI",
        description="CrewAI — multi-agent orchestration framework",
        category=AgentCategory.ORCHESTRATION,
        binary_names=["crewai"],
        pip_packages=["crewai"],
        expected_capabilities=["orchestration", "reasoning", "agents", "swarm"],
        icon="👥",
        license="MIT",
    ),
    ProviderSpec(
        spec_id="autogen",
        name="AutoGen",
        vendor="Microsoft",
        description="AutoGen — multi-agent conversation framework",
        category=AgentCategory.ORCHESTRATION,
        binary_names=["autogen"],
        pip_packages=["pyautogen", "autogen"],
        expected_capabilities=["orchestration", "reasoning", "agents"],
        icon="🔄",
        license="MIT",
    ),
    ProviderSpec(
        spec_id="langgraph",
        name="LangGraph",
        vendor="LangChain",
        description="LangGraph — graph-based agent orchestration",
        category=AgentCategory.ORCHESTRATION,
        binary_names=["langgraph"],
        pip_packages=["langgraph"],
        expected_capabilities=["orchestration", "reasoning", "agents"],
        icon="📊",
        license="MIT",
    ),
    ProviderSpec(
        spec_id="langchain-agents",
        name="LangChain Agents",
        vendor="LangChain",
        description="LangChain — agent framework",
        category=AgentCategory.ORCHESTRATION,
        binary_names=["langchain"],
        pip_packages=["langchain"],
        expected_capabilities=["orchestration", "reasoning", "agents", "rag"],
        icon="🔗",
        license="MIT",
    ),
    ProviderSpec(
        spec_id="semantic-kernel",
        name="Semantic Kernel",
        vendor="Microsoft",
        description="Semantic Kernel — AI orchestration SDK",
        category=AgentCategory.ORCHESTRATION,
        binary_names=["semantic-kernel", "sk"],
        pip_packages=["semantic-kernel"],
        expected_capabilities=["orchestration", "reasoning", "agents"],
        icon="🧠",
        license="MIT",
    ),
    # --- Local LLM Runtimes ---
    ProviderSpec(
        spec_id="ollama",
        name="Ollama",
        vendor="Ollama",
        description="Ollama — local LLM runtime",
        category=AgentCategory.LOCAL_LLM,
        binary_names=["ollama"],
        install_dirs=[".ollama"],
        expected_capabilities=["local_llm", "streaming", "embeddings"],
        config_files=[".ollama/config"],
        env_indicators=["OLLAMA_HOST"],
        icon="🦙",
        license="MIT",
        website="https://ollama.com",
    ),
    ProviderSpec(
        spec_id="lm-studio",
        name="LM Studio",
        vendor="LM Studio",
        description="LM Studio — local LLM runtime with OpenAI-compatible API",
        category=AgentCategory.LOCAL_LLM,
        binary_names=["lms", "lm-studio"],
        expected_capabilities=["local_llm", "streaming", "embeddings"],
        icon="studio",
        license="proprietary",
    ),
    ProviderSpec(
        spec_id="vllm",
        name="vLLM",
        vendor="vLLM",
        description="vLLM — high-throughput LLM inference engine",
        category=AgentCategory.LOCAL_LLM,
        binary_names=["vllm"],
        pip_packages=["vllm"],
        expected_capabilities=["local_llm", "streaming", "embeddings"],
        icon="⚡",
        license="Apache-2.0",
    ),
    ProviderSpec(
        spec_id="jan",
        name="Jan",
        vendor="Jan",
        description="Jan — offline AI assistant",
        category=AgentCategory.LOCAL_LLM,
        binary_names=["jan"],
        expected_capabilities=["local_llm"],
        icon="📅",
        license="AGPL-3.0",
    ),
    ProviderSpec(
        spec_id="anythingllm",
        name="AnythingLLM",
        vendor="Mintplex Labs",
        description="AnythingLLM — local LLM with RAG",
        category=AgentCategory.LOCAL_LLM,
        binary_names=["anythingllm"],
        expected_capabilities=["local_llm", "rag", "embeddings"],
        icon="🌐",
        license="MIT",
    ),
    ProviderSpec(
        spec_id="koboldcpp",
        name="KoboldCPP",
        vendor="KoboldAI",
        description="KoboldCPP — local LLM runtime",
        category=AgentCategory.LOCAL_LLM,
        binary_names=["koboldcpp", "kobold-cpp"],
        expected_capabilities=["local_llm", "streaming"],
        icon="🐉",
        license="AGPL-3.0",
    ),
    ProviderSpec(
        spec_id="localai",
        name="LocalAI",
        vendor="LocalAI",
        description="LocalAI — OpenAI-compatible local AI",
        category=AgentCategory.LOCAL_LLM,
        binary_names=["local-ai", "localai"],
        expected_capabilities=["local_llm", "streaming", "embeddings", "image_generation"],
        icon="🏠",
        license="MIT",
    ),
    ProviderSpec(
        spec_id="llama-cpp",
        name="llama.cpp",
        vendor="Georgi Gerganov",
        description="llama.cpp — LLM inference in C++",
        category=AgentCategory.LOCAL_LLM,
        binary_names=["llama", "llama-cli", "main"],
        expected_capabilities=["local_llm", "streaming"],
        icon="🦙",
        license="MIT",
    ),
    ProviderSpec(
        spec_id="text-generation-webui",
        name="Text Generation WebUI",
        vendor="oobabooga",
        description="Text Generation WebUI — local LLM web interface",
        category=AgentCategory.LOCAL_LLM,
        binary_names=["text-generation-webui", "tgi"],
        expected_capabilities=["local_llm", "streaming"],
        icon="📝",
        license="AGPL-3.0",
    ),
    ProviderSpec(
        spec_id="comfyui",
        name="ComfyUI",
        vendor="Comfy Org",
        description="ComfyUI — image generation workflow engine",
        category=AgentCategory.LOCAL_LLM,
        binary_names=["comfyui"],
        expected_capabilities=["image_generation", "workflow"],
        icon="🎨",
        license="GPL-3.0",
    ),
    # --- Workflow / Automation ---
    ProviderSpec(
        spec_id="n8n",
        name="n8n",
        vendor="n8n",
        description="n8n — workflow automation with AI nodes",
        category=AgentCategory.WORKFLOW,
        binary_names=["n8n"],
        npm_packages=["n8n"],
        expected_capabilities=["workflow", "automation"],
        icon="8️⃣",
        license="Sustainable Use",
    ),
    ProviderSpec(
        spec_id="flowise",
        name="Flowise",
        vendor="FlowiseAI",
        description="Flowise — drag-and-drop AI workflow builder",
        category=AgentCategory.WORKFLOW,
        binary_names=["flowise"],
        npm_packages=["flowise"],
        expected_capabilities=["workflow", "rag"],
        icon="🌊",
        license="Apache-2.0",
    ),
    ProviderSpec(
        spec_id="autogpt",
        name="AutoGPT",
        vendor="Significant Gravitas",
        description="AutoGPT — autonomous AI agent",
        category=AgentCategory.ORCHESTRATION,
        binary_names=["autogpt"],
        pip_packages=["autogpt"],
        expected_capabilities=["autonomy", "reasoning", "terminal", "browser"],
        icon="🤖",
        license="MIT",
    ),
    ProviderSpec(
        spec_id="babyagi",
        name="BabyAGI",
        vendor="Yohei Nakajima",
        description="BabyAGI — task-driven autonomous agent",
        category=AgentCategory.ORCHESTRATION,
        binary_names=["babyagi"],
        pip_packages=["babyagi"],
        expected_capabilities=["autonomy", "reasoning"],
        icon="👶",
        license="MIT",
    ),
    ProviderSpec(
        spec_id="superagi",
        name="SuperAGI",
        vendor="SuperAGI",
        description="SuperAGI — autonomous AI agent framework",
        category=AgentCategory.ORCHESTRATION,
        binary_names=["superagi"],
        pip_packages=["superagi"],
        expected_capabilities=["autonomy", "reasoning", "agents"],
        icon="🦸",
        license="MIT",
    ),
    # --- Cloud CLIs ---
    ProviderSpec(
        spec_id="openai-cli",
        name="OpenAI CLI",
        vendor="OpenAI",
        description="OpenAI CLI — direct OpenAI API access",
        category=AgentCategory.CODING,
        binary_names=["openai", "openai-cli"],
        npm_packages=["openai"],
        pip_packages=["openai"],
        env_indicators=["OPENAI_API_KEY"],
        expected_capabilities=["reasoning", "streaming", "vision", "embeddings"],
        icon="🟢",
        license="MIT",
    ),
    ProviderSpec(
        spec_id="anthropic-cli",
        name="Anthropic CLI",
        vendor="Anthropic",
        description="Anthropic CLI — direct Anthropic API access",
        category=AgentCategory.CODING,
        binary_names=["anthropic", "anthropic-cli"],
        pip_packages=["anthropic"],
        env_indicators=["ANTHROPIC_API_KEY"],
        expected_capabilities=["reasoning", "streaming", "vision"],
        icon="🟠",
        license="MIT",
    ),
    ProviderSpec(
        spec_id="manus",
        name="Manus",
        vendor="Manus",
        description="Manus — autonomous AI agent",
        category=AgentCategory.ORCHESTRATION,
        binary_names=["manus"],
        expected_capabilities=["autonomy", "reasoning", "browser"],
        icon="✋",
        license="proprietary",
    ),
    ProviderSpec(
        spec_id="openmanus",
        name="OpenManus",
        vendor="OpenManus",
        description="OpenManus — open-source autonomous agent",
        category=AgentCategory.ORCHESTRATION,
        binary_names=["openmanus"],
        pip_packages=["openmanus"],
        expected_capabilities=["autonomy", "reasoning", "browser"],
        icon="openhands",
        license="MIT",
    ),
]


# Singleton
_spec_registry: ProviderSpecRegistry | None = None


def get_spec_registry() -> ProviderSpecRegistry:
    """Get the global provider spec registry."""
    global _spec_registry
    if _spec_registry is None:
        _spec_registry = ProviderSpecRegistry()
    return _spec_registry
