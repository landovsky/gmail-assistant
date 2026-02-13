"""Tool interface and registry for the agent framework."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Callable

logger = logging.getLogger(__name__)


@dataclass
class Tool:
    """A tool available to an agent."""

    name: str
    description: str
    parameters: dict[str, Any]
    handler: Callable[..., Any]

    def to_openai_spec(self) -> dict[str, Any]:
        """Convert to OpenAI function-calling tool format."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


class ToolRegistry:
    """Registry for looking up tools by name."""

    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def get_specs(self, tool_names: list[str] | None = None) -> list[dict[str, Any]]:
        """Get OpenAI tool specs for the given tool names (or all if None)."""
        if tool_names is None:
            return [t.to_openai_spec() for t in self._tools.values()]
        return [self._tools[name].to_openai_spec() for name in tool_names if name in self._tools]

    @property
    def names(self) -> list[str]:
        return list(self._tools.keys())

    def execute(self, name: str, arguments: dict[str, Any]) -> Any:
        """Execute a tool by name with the given arguments."""
        tool = self._tools.get(name)
        if not tool:
            return {"error": f"Unknown tool: {name}"}
        try:
            return tool.handler(**arguments)
        except Exception as e:
            logger.error("Tool %s execution failed: %s", name, e)
            return {"error": f"Tool execution failed: {e}"}
