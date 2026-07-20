"""Run summary scaffold — extended by later phases."""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class RunSummary:
    """End-of-run summary; Phase 0 populates MCP discovery fields only."""

    phase: str = "phase_0"
    status: str = "pending"
    started_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    finished_at: str | None = None

    reviews_ingested: int | None = None
    reviews_in_window: int | None = None
    themes_found: list[str] | None = None
    doc_url: str | None = None
    draft_id: str | None = None

    mcp_servers_checked: list[str] = field(default_factory=list)
    mcp_tools_discovered: dict[str, list[str]] = field(default_factory=dict)
    mcp_tool_schemas: dict[str, dict[str, Any]] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)

    def mark_success(self) -> None:
        self.status = "success"
        self.finished_at = datetime.now(timezone.utc).isoformat()

    def mark_failed(self, message: str) -> None:
        self.status = "failed"
        self.finished_at = datetime.now(timezone.utc).isoformat()
        self.errors.append(message)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def log(self, logger: logging.Logger) -> None:
        logger.info("Run summary: %s", json.dumps(self.to_dict(), indent=2, default=str))

    def print_summary(self) -> None:
        print("\n=== Weekly Pulse - Run Summary ===")
        print(f"Phase:     {self.phase}")
        print(f"Status:    {self.status}")
        print(f"Started:   {self.started_at}")
        if self.finished_at:
            print(f"Finished:  {self.finished_at}")
        if self.mcp_servers_checked:
            print(f"MCP servers checked: {', '.join(self.mcp_servers_checked)}")
        if self.mcp_tools_discovered:
            print("MCP tools discovered:")
            for server, tools in self.mcp_tools_discovered.items():
                print(f"  {server}: {', '.join(tools) if tools else '(none)'}")
        if self.mcp_tool_schemas:
            print("MCP tool schemas (create targets):")
            for name, schema in self.mcp_tool_schemas.items():
                print(f"  {name}: {json.dumps(schema, indent=4)}")
        if self.errors:
            print("Errors:")
            for err in self.errors:
                print(f"  - {err}")
        print("==================================\n")
