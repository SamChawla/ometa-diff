"""MCP server exposing metadata diff tools for OpenMetadata."""

from __future__ import annotations

import importlib.util
from typing import Any

_mcp_available = importlib.util.find_spec("mcp") is not None


def create_server() -> Any:
    """Build and return the MCP server with all three tools registered.

    Returns:
        Configured MCP Server instance.

    Raises:
        ImportError: If the 'mcp' extra is not installed.
    """
    if not _mcp_available:
        raise ImportError("MCP SDK not installed. Run: pip install 'ometa-diff[mcp]'")
    raise NotImplementedError


def run() -> None:
    """Entry point: start the MCP server over STDIO transport."""
    raise NotImplementedError
