"""Amunty tools — system tools for the PC assistant."""

from amunty.services.tools.registry import tool_registry
from amunty.services.tools.system_tools import register_system_tools

# Auto-register all system tools
register_system_tools(tool_registry)
