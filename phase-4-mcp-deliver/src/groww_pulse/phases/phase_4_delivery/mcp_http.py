"""HTTP client for Google MCP tool server (FastAPI REST)."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any

import httpx

logger = logging.getLogger("groww_pulse.deliver")


class McpToolError(Exception):
    """Raised when an MCP HTTP tool call fails."""


@dataclass
class ToolDiscovery:
    base_url: str
    tools: list[str] = field(default_factory=list)
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.error is None


@dataclass
class GoogleMcpHttpClient:
    """Client for https://github.com/ArpitDumka/Google-mcp-server REST tools."""

    base_url: str
    append_tool: str = "append_to_doc"
    draft_tool: str = "create_email_draft"
    timeout_sec: float = 60.0
    max_retries: int = 2

    def _url(self, tool_path: str) -> str:
        path = tool_path if tool_path.startswith("/") else f"/{tool_path}"
        return f"{self.base_url.rstrip('/')}{path}"

    def discover_tools(self) -> ToolDiscovery:
        result = ToolDiscovery(base_url=self.base_url, tools=[self.append_tool, self.draft_tool])
        try:
            with httpx.Client(timeout=self.timeout_sec) as client:
                response = client.get(self._url("/openapi.json"))
                if response.status_code == 200:
                    schema = response.json()
                    paths = schema.get("paths", {})
                    result.tools = sorted(paths.keys())
                    return result
                response = client.get(self._url("/docs"))
                if response.status_code != 200:
                    result.error = f"Server unreachable at {self.base_url} (status {response.status_code})"
        except httpx.HTTPError as exc:
            result.error = f"Cannot reach MCP server at {self.base_url}: {exc}"
        return result

    def _post_tool(self, tool_path: str, payload: dict[str, Any]) -> dict[str, Any]:
        url = self._url(tool_path)
        last_error: Exception | None = None

        for attempt in range(self.max_retries + 1):
            try:
                with httpx.Client(timeout=self.timeout_sec) as client:
                    response = client.post(url, json=payload)
                if response.status_code >= 500 and attempt < self.max_retries:
                    time.sleep(0.5 * (attempt + 1))
                    continue
                response.raise_for_status()
                data = response.json()
                if isinstance(data, dict) and data.get("status") == "error":
                    raise McpToolError(data.get("message", "tool returned error"))
                return data if isinstance(data, dict) else {"result": data}
            except (httpx.HTTPError, McpToolError) as exc:
                last_error = exc
                if attempt < self.max_retries:
                    time.sleep(0.5 * (attempt + 1))
                    continue
                break

        raise McpToolError(f"Tool {tool_path} failed after retries: {last_error}") from last_error

    def append_to_doc(self, doc_id: str, content: str) -> dict[str, Any]:
        logger.info("Calling MCP tool %s for doc_id=%s", self.append_tool, doc_id)
        return self._post_tool(self.append_tool, {"doc_id": doc_id, "content": content})

    def create_email_draft(self, to: str, subject: str, body: str) -> dict[str, Any]:
        logger.info("Calling MCP tool %s for recipient=%s", self.draft_tool, to)
        return self._post_tool(self.draft_tool, {"to": to, "subject": subject, "body": body})

    @staticmethod
    def doc_url_from_id(doc_id: str) -> str:
        return f"https://docs.google.com/document/d/{doc_id}/edit"
