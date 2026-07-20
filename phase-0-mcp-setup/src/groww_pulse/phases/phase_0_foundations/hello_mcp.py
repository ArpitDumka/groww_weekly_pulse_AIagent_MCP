"""Phase 0 entrypoint: config check + MCP tool discovery."""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys

from groww_pulse.config import Settings, load_settings
from groww_pulse.logging_setup import setup_logging
from groww_pulse.mcp.discovery import discover_tools
from groww_pulse.run_summary import RunSummary


async def run_mcp_discovery(settings: Settings, summary: RunSummary, logger: logging.Logger) -> int:
    """Connect to configured MCP servers, list tools, and read create-tool schemas."""
    try:
        servers = settings.require_mcp_servers()
    except ValueError as exc:
        summary.mark_failed(str(exc))
        logger.error("%s", exc)
        return 1

    exit_code = 0

    for name, cfg in servers.items():
        summary.mcp_servers_checked.append(name)
        logger.info("Discovering tools on MCP server '%s'...", name)
        result = await discover_tools(cfg)

        summary.mcp_tools_discovered[name] = result.tools
        summary.mcp_tool_schemas.update(
            {f"{name}.{tool}": schema for tool, schema in result.tool_schemas.items()}
        )

        if result.error:
            summary.errors.append(f"{name}: {result.error}")
            exit_code = 1
        elif result.missing_expected:
            missing = ", ".join(result.missing_expected)
            summary.errors.append(f"{name}: missing expected tool(s): {missing}")
            exit_code = 1
        elif cfg.create_tool and not result.create_tool_found:
            summary.errors.append(f"{name}: create tool '{cfg.create_tool}' not found")
            exit_code = 1

    if exit_code == 0:
        summary.mark_success()
    else:
        summary.status = "failed"

    return exit_code


def run_config_check(settings: Settings, summary: RunSummary, logger: logging.Logger) -> int:
    """Validate settings and log config snapshot (no MCP connection)."""
    logger.info("Configuration loaded successfully.")
    logger.info(
        "Pipeline settings: window=%sw, max_themes=%s, top_themes=%s, "
        "quotes=%s, actions=%s, word_budget=%s, recipient=%s, dry_run=%s",
        settings.window_weeks,
        settings.max_themes,
        settings.top_themes,
        settings.quote_count,
        settings.action_count,
        settings.word_budget,
        settings.recipient,
        settings.dry_run,
    )

    servers = settings.mcp_servers()
    for name, cfg in servers.items():
        state = "configured" if cfg.is_configured else "NOT configured"
        logger.info("MCP server '%s': %s (%s)", name, state, cfg.command or "no command")

    summary.mark_success()
    summary.mcp_servers_checked = list(servers.keys())
    return 0


async def async_main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Phase 0 — validate config and discover Google Docs / Gmail MCP tools.",
    )
    parser.add_argument(
        "--config-only",
        action="store_true",
        help="Validate .env settings only; do not connect to MCP servers.",
    )
    args = parser.parse_args(argv)

    logger = setup_logging()
    summary = RunSummary(phase="phase_0_foundations")

    try:
        settings = load_settings()
    except Exception as exc:
        summary.mark_failed(f"Config error: {exc}")
        summary.print_summary()
        logger.exception("Failed to load configuration")
        return 1

    if args.config_only:
        code = run_config_check(settings, summary, logger)
    else:
        code = await run_mcp_discovery(settings, summary, logger)

    summary.log(logger)
    summary.print_summary()
    return code


def main() -> None:
    raise SystemExit(asyncio.run(async_main()))


if __name__ == "__main__":
    main()
