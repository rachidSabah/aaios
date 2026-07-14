"""Calculator plugin example — provides a calculator tool."""

from __future__ import annotations

import ast
import operator
from typing import Any

from services.plugin.sdk import PluginManifestBuilder

manifest = (
    PluginManifestBuilder("calculator", "1.0.0")
    .description("A simple calculator tool")
    .vendor("AAiOS")
    .provides_tools("calculator_plugin.register_tools")
    .entry_point("calculator_plugin")
    .build()
)


# Safe operators for expression evaluation
_SAFE_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.Mod: operator.mod,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}


def _safe_eval(expr: str) -> float:
    """Safely evaluate a math expression (no builtins, no attributes)."""
    node = ast.parse(expr, mode="eval").body
    return _eval_node(node)


def _eval_node(node: ast.AST) -> float:
    """Recursively evaluate an AST node."""
    if isinstance(node, ast.Constant) and isinstance(node.value, int | float):
        return float(node.value)
    if isinstance(node, ast.BinOp):
        op = _SAFE_OPS.get(type(node.op))
        if op is None:
            raise ValueError(f"Unsupported operator: {type(node.op).__name__}")
        return op(_eval_node(node.left), _eval_node(node.right))
    if isinstance(node, ast.UnaryOp):
        op = _SAFE_OPS.get(type(node.op))
        if op is None:
            raise ValueError(f"Unsupported operator: {type(node.op).__name__}")
        return op(_eval_node(node.operand))
    raise ValueError(f"Unsupported expression: {ast.dump(node)}")


def register_tools() -> None:
    """Register the calculator tool with the Tool Registry."""
    from core.registry import Tool, ToolCallContext, get_tool_registry

    async def calculate(args: dict[str, Any], ctx: ToolCallContext) -> dict[str, Any]:
        """Evaluate a math expression.

        Args:
            expression: The math expression (e.g. "2 + 3 * 4").
        """
        expr = args.get("expression", "0")
        try:
            result = _safe_eval(expr)
            return {"expression": expr, "result": result}
        except Exception as e:
            return {"expression": expr, "error": str(e)}

    registry = get_tool_registry()
    registry.register(
        Tool(
            name="calculator.evaluate",
            description="Evaluate a math expression safely",
            input_schema={
                "type": "object",
                "properties": {"expression": {"type": "string", "description": "Math expression"}},
                "required": ["expression"],
            },
            permission=None,
            handler=calculate,
        )
    )
