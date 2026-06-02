"""Tool registry — maps tool names to implementations and JSON schemas."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Awaitable

logger = logging.getLogger("amunty.tools")


@dataclass
class ToolDef:
    """A registered tool with its schema and executor."""
    name: str
    description: str
    parameters: dict[str, Any]
    execute: Callable[..., Awaitable[str]]


class ToolRegistry:
    """Central registry for all available tools."""

    def __init__(self) -> None:
        self._tools: dict[str, ToolDef] = {}

    def register(
        self,
        name: str,
        description: str,
        parameters: dict[str, Any],
        execute: Callable[..., Awaitable[str]],
    ) -> None:
        """Register a tool."""
        self._tools[name] = ToolDef(
            name=name,
            description=description,
            parameters=parameters,
            execute=execute,
        )
        logger.info("Registered tool: %s", name)

    def get_schemas(self) -> list[dict]:
        """Return OpenAI-format tool schemas for the LLM."""
        schemas = []
        for tool in self._tools.values():
            schemas.append({
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.parameters,
                },
            })
        return schemas

    async def execute(self, name: str, arguments: str | dict) -> str:
        """Execute a tool by name with the given arguments."""
        tool = self._tools.get(name)
        if not tool:
            return f"Error: Unknown tool '{name}'"

        from amunty.services.tools.security import blocked_tools_for_owner
        blocked = blocked_tools_for_owner(None)  # Pass user ID here when auth is implemented
        if name in blocked:
            return f"Error: You do not have permission to execute '{name}'."

        try:
            if isinstance(arguments, str):
                args = json.loads(arguments) if arguments else {}
            else:
                args = arguments

            result = await tool.execute(**args)
            return str(result)
        except json.JSONDecodeError:
            return f"Error: Invalid JSON arguments for '{name}'"
        except Exception as exc:
            logger.error("Tool '%s' failed: %s", name, exc, exc_info=True)
            return f"Error executing '{name}': {exc}"

    @property
    def tool_names(self) -> list[str]:
        return list(self._tools.keys())

    def __len__(self) -> int:
        return len(self._tools)


# Global singleton
tool_registry = ToolRegistry()
