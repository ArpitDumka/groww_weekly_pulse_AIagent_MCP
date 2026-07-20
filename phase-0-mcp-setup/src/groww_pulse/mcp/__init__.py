"""MCP integration layer (MCP-first; no direct Google API clients)."""

from groww_pulse.mcp.client import McpConnectionError, connect_server
from groww_pulse.mcp.discovery import ToolDiscoveryResult, discover_tools

__all__ = [
    "McpConnectionError",
    "ToolDiscoveryResult",
    "connect_server",
    "discover_tools",
]
