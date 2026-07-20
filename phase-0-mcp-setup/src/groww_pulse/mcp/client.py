"""MCP stdio client helpers."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from groww_pulse.config import McpServerConfig

logger = logging.getLogger("groww_pulse.mcp")


class McpConnectionError(Exception):
    """Raised when an MCP server cannot be reached or initialized."""


@asynccontextmanager
async def connect_server(cfg: McpServerConfig) -> AsyncIterator[ClientSession]:
    """Connect to an MCP server over stdio and yield an initialized session."""
    if not cfg.is_configured:
        raise McpConnectionError(
            f"MCP server '{cfg.name}' is not configured (missing command)."
        )

    logger.info(
        "Connecting to MCP server '%s': %s %s",
        cfg.name,
        cfg.command,
        " ".join(cfg.args),
    )

    params = StdioServerParameters(command=cfg.command, args=cfg.args)

    try:
        async with stdio_client(params) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                init_result = await session.initialize()
                logger.info(
                    "MCP server '%s' initialized: %s",
                    cfg.name,
                    init_result.serverInfo.name if init_result.serverInfo else "unknown",
                )
                yield session
    except McpConnectionError:
        raise
    except Exception as exc:
        raise McpConnectionError(
            f"Failed to connect to MCP server '{cfg.name}': {exc}"
        ) from exc
