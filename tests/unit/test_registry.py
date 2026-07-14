"""Tests for core.registry — Tool Registry + Prompt Registry."""

from __future__ import annotations

import pytest

from core.contracts.actor import ActorRef
from core.contracts.permission import Permission
from core.registry import (
    Prompt,
    PromptNotFoundError,
    PromptRegistry,
    PromptRenderError,
    Tool,
    ToolCallContext,
    ToolNotFoundError,
    ToolRegistry,
    get_prompt_registry,
    get_tool_registry,
    set_prompt_registry,
    set_tool_registry,
)


@pytest.fixture(autouse=True)
def _reset_registries():
    """Reset the singleton registries before each test."""
    set_tool_registry(ToolRegistry())
    set_prompt_registry(PromptRegistry())
    yield
    set_tool_registry(ToolRegistry())
    set_prompt_registry(PromptRegistry())


@pytest.mark.offline
class TestToolRegistry:
    """Tool Registry tests."""

    async def test_register_and_get(self) -> None:
        async def handler(args, ctx):  # type: ignore[no-untyped-def]
            return {"echo": args.get("msg", "")}

        registry = get_tool_registry()
        tool = Tool(
            name="test.echo",
            description="Echoes a message",
            input_schema={"type": "object", "properties": {"msg": {"type": "string"}}},
            permission=Permission(name="tool.call"),
            handler=handler,
        )
        registry.register(tool)
        assert registry.has("test.echo")
        fetched = registry.get("test.echo")
        assert fetched.name == "test.echo"

    async def test_get_unknown_raises(self) -> None:
        registry = get_tool_registry()
        with pytest.raises(ToolNotFoundError):
            registry.get("does.not.exist")

    async def test_unregister(self) -> None:
        async def handler(args, ctx):  # type: ignore[no-untyped-def]
            return None

        registry = get_tool_registry()
        registry.register(Tool(name="temp.tool", handler=handler))
        assert registry.unregister("temp.tool") is True
        assert registry.has("temp.tool") is False
        # Unregistering again returns False
        assert registry.unregister("temp.tool") is False

    async def test_list_with_prefix(self) -> None:
        async def h(args, ctx):  # type: ignore[no-untyped-def]
            return None

        registry = get_tool_registry()
        registry.register(Tool(name="slack.send", handler=h))
        registry.register(Tool(name="slack.list", handler=h))
        registry.register(Tool(name="github.create_issue", handler=h))
        slack_tools = registry.list("slack.")
        assert len(slack_tools) == 2
        all_tools = registry.list()
        assert len(all_tools) == 3

    async def test_call_returns_result(self) -> None:
        async def echo(args, ctx):  # type: ignore[no-untyped-def]
            return {"echo": args.get("msg")}

        registry = get_tool_registry()
        registry.register(Tool(name="test.echo", handler=echo))
        ctx = ToolCallContext(actor=ActorRef.system(), correlation_id="test")
        result = await registry.call("test.echo", {"msg": "hello"}, ctx)
        assert result.success is True
        assert result.output == {"echo": "hello"}

    async def test_call_unknown_returns_failure(self) -> None:
        registry = get_tool_registry()
        ctx = ToolCallContext(actor=ActorRef.system(), correlation_id="test")
        result = await registry.call("no.such.tool", {}, ctx)
        assert result.success is False
        assert "not found" in (result.error or "")

    async def test_call_with_handler_error(self) -> None:
        async def failing(args, ctx):  # type: ignore[no-untyped-def]
            raise ValueError("boom")

        registry = get_tool_registry()
        registry.register(Tool(name="test.failing", handler=failing))
        ctx = ToolCallContext(actor=ActorRef.system(), correlation_id="test")
        result = await registry.call("test.failing", {}, ctx)
        assert result.success is False
        assert "boom" in (result.error or "")


@pytest.mark.offline
class TestPromptRegistry:
    """Prompt Registry tests."""

    def test_register_and_render(self) -> None:
        registry = get_prompt_registry()
        registry.register(
            Prompt(
                name="test.greet",
                version="1.0.0",
                template="Hello, {{name}}!",
                inputs=["name"],
                outputs=["text"],
            )
        )
        rendered = registry.render("test.greet", name="World")
        assert rendered == "Hello, World!"

    def test_get_latest_version(self) -> None:
        registry = get_prompt_registry()
        registry.register(Prompt(name="p", version="1.0.0", template="v1", inputs=[]))
        registry.register(Prompt(name="p", version="2.0.0", template="v2", inputs=[]))
        latest = registry.get("p")
        assert latest.version == "2.0.0"

    def test_get_specific_version(self) -> None:
        registry = get_prompt_registry()
        registry.register(Prompt(name="p", version="1.0.0", template="v1", inputs=[]))
        registry.register(Prompt(name="p", version="2.0.0", template="v2", inputs=[]))
        v1 = registry.get("p", "1.0.0")
        assert v1.template == "v1"

    def test_get_unknown_raises(self) -> None:
        registry = get_prompt_registry()
        with pytest.raises(PromptNotFoundError):
            registry.get("does.not.exist")

    def test_render_missing_input_raises(self) -> None:
        registry = get_prompt_registry()
        registry.register(
            Prompt(
                name="p",
                version="1.0.0",
                template="Hello {{name}}!",
                inputs=["name"],
            )
        )
        # Don't pass the required 'name' input at all
        with pytest.raises(PromptRenderError, match="missing inputs"):
            registry.render("p")  # type: ignore[call-arg]

    def test_render_invalid_template_raises(self) -> None:
        registry = get_prompt_registry()
        registry.register(
            Prompt(
                name="p",
                version="1.0.0",
                template="Hello {{ name }",  # invalid Jinja2
                inputs=[],
            )
        )
        with pytest.raises(PromptRenderError):
            registry.render("p")

    def test_unregister_specific_version(self) -> None:
        registry = get_prompt_registry()
        registry.register(Prompt(name="p", version="1.0.0", template="v1", inputs=[]))
        registry.register(Prompt(name="p", version="2.0.0", template="v2", inputs=[]))
        count = registry.unregister("p", "1.0.0")
        assert count == 1
        assert registry.has("p") is True
        assert not registry.has("p", "1.0.0")

    def test_unregister_all_versions(self) -> None:
        registry = get_prompt_registry()
        registry.register(Prompt(name="p", version="1.0.0", template="v1", inputs=[]))
        registry.register(Prompt(name="p", version="2.0.0", template="v2", inputs=[]))
        count = registry.unregister("p")
        assert count == 2
        assert not registry.has("p")

    def test_list_with_prefix(self) -> None:
        registry = get_prompt_registry()
        registry.register(Prompt(name="rag.answer", version="1.0.0", template="x", inputs=[]))
        registry.register(Prompt(name="rag.summarize", version="1.0.0", template="x", inputs=[]))
        registry.register(
            Prompt(name="planner.decompose", version="1.0.0", template="x", inputs=[])
        )
        rag_prompts = registry.list("rag.")
        assert len(rag_prompts) == 2

    def test_semver_sorting(self) -> None:
        registry = get_prompt_registry()
        registry.register(Prompt(name="p", version="1.10.0", template="v110", inputs=[]))
        registry.register(Prompt(name="p", version="1.2.0", template="v12", inputs=[]))
        registry.register(Prompt(name="p", version="1.1.0", template="v11", inputs=[]))
        latest = registry.get("p")
        assert latest.version == "1.10.0"  # not '1.2.0' as string sort would give
