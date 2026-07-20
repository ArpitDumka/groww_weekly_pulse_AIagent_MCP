"""MCP tool discovery and schema inspection."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from mcp.types import Tool

from groww_pulse.config import McpServerConfig
from groww_pulse.mcp.client import McpConnectionError, connect_server

logger = logging.getLogger("groww_pulse.mcp")


@dataclass
class ToolDiscoveryResult:
    server_name: str
    tools: list[str] = field(default_factory=list)
    tool_schemas: dict[str, dict[str, Any]] = field(default_factory=dict)
    missing_expected: list[str] = field(default_factory=list)
    create_tool: str | None = None
    create_tool_found: bool = False
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.error is None and not self.missing_expected and self.create_tool_found


def _tool_to_schema(tool: Tool) -> dict[str, Any]:
    schema: dict[str, Any] = {
        "name": tool.name,
        "description": tool.description,
    }
    if tool.inputSchema:
        schema["inputSchema"] = tool.inputSchema
    return schema


def _find_tool(tools: list[Tool], name: str) -> Tool | None:
    for tool in tools:
        if tool.name == name:
            return tool
    return None


async def discover_tools(cfg: McpServerConfig) -> ToolDiscoveryResult:
    """List tools on an MCP server and read schemas for expected/create tools."""
    result = ToolDiscoveryResult(server_name=cfg.name, create_tool=cfg.create_tool)

    try:
        async with connect_server(cfg) as session:
            listed = await session.list_tools()
            tool_list = listed.tools
            result.tools = [t.name for t in tool_list]

            logger.info(
                "MCP server '%s' exposes %d tool(s): %s",
                cfg.name,
                len(result.tools),
                ", ".join(result.tools) or "(none)",
            )

            for expected in cfg.expected_tools:
                if expected not in result.tools:
                    result.missing_expected.append(expected)

            if cfg.create_tool:
                create = _find_tool(tool_list, cfg.create_tool)
                if create:
                    result.create_tool_found = True
                    result.tool_schemas[cfg.create_tool] = _tool_to_schema(create)
                    logger.info(
                        "Schema for '%s'.'%s': %s",
                        cfg.name,
                        cfg.create_tool,
                        result.tool_schemas[cfg.create_tool].get("inputSchema"),
                    )
                else:
                    result.missing_expected.append(cfg.create_tool)

            for name in cfg.expected_tools:
                if name in result.tool_schemas:
                    continue
                tool = _find_tool(tool_list, name)
                if tool:
                    result.tool_schemas[name] = _tool_to_schema(tool)

    except McpConnectionError as exc:
        result.error = str(exc)
        logger.error("Discovery failed for '%s': %s", cfg.name, exc)

    return result
