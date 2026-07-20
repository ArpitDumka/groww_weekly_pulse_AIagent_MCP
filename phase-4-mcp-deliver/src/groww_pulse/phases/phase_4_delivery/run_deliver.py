"""CLI entrypoint for Phase 4 delivery."""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

from groww_pulse.config import load_settings
from groww_pulse.logging_setup import setup_logging
from groww_pulse.phases.phase_4_delivery.io import load_pulse
from groww_pulse.phases.phase_4_delivery.pipeline import deliver_pulse


def main() -> None:
    parser = argparse.ArgumentParser(description="Deliver Phase 3 pulse via Google MCP server.")
    parser.add_argument("--input", type=Path, help="Pulse JSON (default from .env)")
    parser.add_argument("--dry-run", action="store_true", help="Force DRY_RUN preview artifacts")
    parser.add_argument("--discover-only", action="store_true", help="Only probe MCP server tools")
    args = parser.parse_args()

    logger = setup_logging()
    settings = load_settings()
    if args.dry_run:
        settings = settings.model_copy(update={"dry_run": True})

    if args.discover_only:
        from groww_pulse.phases.phase_4_delivery.mcp_http import GoogleMcpHttpClient

        client = GoogleMcpHttpClient(
            base_url=settings.mcp_server_base_url,
            append_tool=settings.mcp_append_tool,
            draft_tool=settings.mcp_draft_tool,
        )
        discovery = client.discover_tools()
        print(json.dumps({"base_url": discovery.base_url, "tools": discovery.tools, "error": discovery.error}, indent=2))
        raise SystemExit(0 if discovery.ok else 1)

    pulse_path = args.input or settings.phase3_pulse_input
    if not pulse_path.is_file():
        raise SystemExit(f"Pulse input not found: {pulse_path}. Run Phase 3 first.")

    pulse = load_pulse(pulse_path)
    logger.info("Loaded pulse for week_of=%s from %s", pulse.week_of, pulse_path)

    result, report = deliver_pulse(pulse, settings)
    output = {
        "delivery": result.model_dump(mode="json"),
        "report": report,
    }
    out_path = settings.delivery_state_path.parent / "delivery_result.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(output, indent=2, default=str), encoding="utf-8")

    print(json.dumps(output, indent=2, default=str))

    if not result.ok and not result.dry_run:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
