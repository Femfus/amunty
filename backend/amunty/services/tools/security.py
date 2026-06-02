"""Server-side tool safety policy."""

from __future__ import annotations

import logging
from typing import Optional, Set

logger = logging.getLogger("amunty.tools.security")

# Tools regular/public users must not execute directly.
NON_ADMIN_BLOCKED_TOOLS = {
    "run_command",
    "get_clipboard",
    "open_application",
    "open_url",
    "list_directory",
}

def is_public_blocked_tool(tool_name: Optional[str]) -> bool:
    """Return True when a non-admin/public user must not execute this tool."""
    if not tool_name:
        return False
    return tool_name in NON_ADMIN_BLOCKED_TOOLS or tool_name.startswith("mcp_")


def owner_is_admin_or_single_user(owner: Optional[str]) -> bool:
    """Return True for admins. For Amunty's local-first architecture, default to True unless multi-user is added."""
    # In a local app, the owner is inherently the admin.
    return True


def blocked_tools_for_owner(owner: Optional[str]) -> Set[str]:
    """Tools to hide/disable for this owner under public-user policy."""
    if owner_is_admin_or_single_user(owner):
        return set()
    return set(NON_ADMIN_BLOCKED_TOOLS)
