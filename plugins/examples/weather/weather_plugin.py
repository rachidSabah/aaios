"""Weather plugin example — provides a weather lookup tool."""

from __future__ import annotations

from typing import Any

from services.plugin.sdk import PluginManifestBuilder

manifest = (
    PluginManifestBuilder("weather", "1.0.0")
    .description("Get current weather for any city")
    .vendor("AAiOS")
    .provides_tools("weather_plugin.register_tools")
    .requires_permissions("gateway.net.request")
    .requires_api_keys("weather/api_key")
    .entry_point("weather_plugin")
    .build()
)


def register_tools() -> None:
    """Register the weather tool with the Tool Registry."""
    from core.registry import Tool, ToolCallContext, get_tool_registry

    async def get_weather(args: dict[str, Any], ctx: ToolCallContext) -> dict[str, Any]:
        """Get the current weather for a city.

        Args:
            city: The city name.
        """
        city = args.get("city", "Unknown")
        # Phase 11 mock — in production, this would call a real weather API
        # via the Gateway's network sub-gateway
        return {
            "city": city,
            "temperature_c": 22,
            "condition": "sunny",
            "humidity": 45,
            "wind_kmh": 10,
        }

    registry = get_tool_registry()
    registry.register(
        Tool(
            name="weather.get",
            description="Get current weather for a city",
            input_schema={
                "type": "object",
                "properties": {"city": {"type": "string", "description": "City name"}},
                "required": ["city"],
            },
            permission=None,  # set by the Tool Registry
            handler=get_weather,
        )
    )
