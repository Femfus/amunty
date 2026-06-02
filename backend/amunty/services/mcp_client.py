"""MCP Client manager for bridging MCP servers into the tool registry."""

from __future__ import annotations

import logging
import os
import shlex
from contextlib import AsyncExitStack

from mcp.client.session import ClientSession
from mcp.client.stdio import stdio_client, StdioServerParameters

from amunty.config import settings
from amunty.services.tools.registry import tool_registry

logger = logging.getLogger("amunty.mcp")


class MCPManager:
    """Manages MCP server processes and bridges their tools to the AI."""

    def __init__(self) -> None:
        self._sessions: dict[str, ClientSession] = {}
        self._exit_stack: AsyncExitStack | None = None

    async def initialize(self) -> None:
        """Start all configured MCP servers and register their tools."""
        if not settings.mcp_servers:
            logger.info("No MCP servers configured. Add them to settings.mcp_servers or .env to enable.")
            return

        self._exit_stack = AsyncExitStack()

        for idx, cmd_str in enumerate(settings.mcp_servers):
            await self._start_server(f"mcp_server_{idx}", cmd_str)

    async def _start_server(self, server_id: str, cmd_str: str) -> None:
        """Spawn a single MCP server via stdio and register its tools."""
        try:
            parts = shlex.split(cmd_str)
            if not parts:
                return
            
            command = parts[0]
            args = parts[1:]
            
            # Windows resolution for npx
            if os.name == "nt" and command == "npx":
                command = "npx.cmd"
                
            server_params = StdioServerParameters(
                command=command,
                args=args,
                env=None
            )
            
            assert self._exit_stack is not None
            
            # Connect over stdio
            read, write = await self._exit_stack.enter_async_context(stdio_client(server_params))
            session = await self._exit_stack.enter_async_context(ClientSession(read, write))
            
            await session.initialize()
            self._sessions[server_id] = session
            
            # List tools
            result = await session.list_tools()
            
            # Bridge each tool into Amunty's tool_registry
            for tool in result.tools:
                # We prefix the tool name to avoid collisions
                safe_name = f"{server_id}_{tool.name}".replace("-", "_")
                
                tool_registry.register(
                    name=safe_name,
                    description=f"[MCP: {command}] {tool.description or tool.name}",
                    parameters=tool.inputSchema,
                    execute=self._make_executor(server_id, tool.name)
                )
                
            logger.info("MCP server started: '%s' (registered %d tools)", command, len(result.tools))
            
        except Exception as exc:
            logger.error("Failed to start MCP server '%s': %s", cmd_str, exc)

    def _make_executor(self, server_id: str, original_tool_name: str):
        """Create a closure that executes the tool on the MCP session."""
        async def _execute(**kwargs) -> str:
            try:
                session = self._sessions.get(server_id)
                if not session:
                    return f"Error: MCP session {server_id} is dead."
                    
                result = await session.call_tool(original_tool_name, arguments=kwargs)
                
                # Extract text content from the MCP result
                output = []
                for content in result.content:
                    if getattr(content, "type", "text") == "text":
                        output.append(content.text)
                        
                return "\n".join(output)
            except Exception as exc:
                logger.error("MCP tool '%s' failed: %s", original_tool_name, exc)
                return f"Error from MCP server: {exc}"
                
        return _execute

    async def shutdown(self) -> None:
        """Close all MCP server sessions."""
        if self._exit_stack:
            await self._exit_stack.aclose()
            self._exit_stack = None
            logger.info("All MCP server sessions closed.")


# Singleton instance
mcp_manager = MCPManager()
