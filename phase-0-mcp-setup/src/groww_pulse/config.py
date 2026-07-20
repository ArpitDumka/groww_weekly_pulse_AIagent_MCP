"""Application configuration loaded from environment / optional MCP JSON."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class McpServerConfig:
    """Launch parameters for a single MCP server (stdio)."""

    __slots__ = ("name", "command", "args", "expected_tools", "create_tool")

    def __init__(
        self,
        name: str,
        command: str,
        args: list[str],
        expected_tools: list[str] | None = None,
        create_tool: str | None = None,
    ) -> None:
        self.name = name
        self.command = command
        self.args = args
        self.expected_tools = expected_tools or []
        self.create_tool = create_tool

    @property
    def is_configured(self) -> bool:
        return bool(self.command.strip())

    def __repr__(self) -> str:
        return f"McpServerConfig(name={self.name!r}, command={self.command!r}, args={self.args!r})"


class Settings(BaseSettings):
    """Runtime settings for the weekly pulse pipeline."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    window_weeks: int = Field(default=12, ge=8, le=12, alias="WINDOW_WEEKS")
    max_themes: int = Field(default=5, ge=1, le=5, alias="MAX_THEMES")
    top_themes: int = Field(default=3, ge=1, alias="TOP_THEMES")
    quote_count: int = Field(default=3, ge=1, alias="QUOTE_COUNT")
    action_count: int = Field(default=3, ge=1, alias="ACTION_COUNT")
    word_budget: int = Field(default=250, ge=1, le=250, alias="WORD_BUDGET")
    recipient: str = Field(alias="RECIPIENT")
    dry_run: bool = Field(default=False, alias="DRY_RUN")

    mcp_servers_config: Path | None = Field(default=None, alias="MCP_SERVERS_CONFIG")

    google_docs_mcp_command: str = Field(default="", alias="GOOGLE_DOCS_MCP_COMMAND")
    google_docs_mcp_args: str = Field(default="", alias="GOOGLE_DOCS_MCP_ARGS")
    gmail_mcp_command: str = Field(default="", alias="GMAIL_MCP_COMMAND")
    gmail_mcp_args: str = Field(default="", alias="GMAIL_MCP_ARGS")

    google_docs_create_tool: str = Field(default="create_document", alias="GOOGLE_DOCS_CREATE_TOOL")
    gmail_create_draft_tool: str = Field(default="create_draft", alias="GMAIL_CREATE_DRAFT_TOOL")

    @field_validator("recipient")
    @classmethod
    def recipient_not_empty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("RECIPIENT must not be empty")
        if "@" not in value:
            raise ValueError("RECIPIENT must look like an email address")
        return value.strip()

    @model_validator(mode="after")
    def top_themes_within_max(self) -> Settings:
        if self.top_themes > self.max_themes:
            raise ValueError("TOP_THEMES must be <= MAX_THEMES")
        return self

    @staticmethod
    def _parse_args(raw: str | list[str]) -> list[str]:
        if isinstance(raw, list):
            return [str(a) for a in raw]
        if not raw.strip():
            return []
        return raw.split()

    def _server_from_env(
        self,
        name: str,
        command: str,
        args_raw: str,
        create_tool: str,
        default_expected: list[str],
    ) -> McpServerConfig:
        return McpServerConfig(
            name=name,
            command=command.strip(),
            args=self._parse_args(args_raw),
            expected_tools=default_expected,
            create_tool=create_tool,
        )

    def _load_mcp_json(self) -> dict[str, McpServerConfig]:
        if self.mcp_servers_config is None:
            return {}
        path = self.mcp_servers_config
        if not path.is_file():
            raise FileNotFoundError(f"MCP_SERVERS_CONFIG not found: {path}")

        raw: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
        servers: dict[str, McpServerConfig] = {}
        for name, cfg in raw.get("servers", {}).items():
            servers[name] = McpServerConfig(
                name=name,
                command=str(cfg["command"]).strip(),
                args=self._parse_args(cfg.get("args", [])),
                expected_tools=list(cfg.get("expected_tools", [])),
                create_tool=cfg.get("create_tool"),
            )
        return servers

    def mcp_servers(self) -> dict[str, McpServerConfig]:
        """Resolved MCP server configs (JSON file overrides env when present)."""
        from_json = self._load_mcp_json()
        if from_json:
            return from_json

        return {
            "google_docs": self._server_from_env(
                "google_docs",
                self.google_docs_mcp_command,
                self.google_docs_mcp_args,
                self.google_docs_create_tool,
                ["create_document", "update_document"],
            ),
            "gmail": self._server_from_env(
                "gmail",
                self.gmail_mcp_command,
                self.gmail_mcp_args,
                self.gmail_create_draft_tool,
                ["create_draft"],
            ),
        }

    def require_mcp_servers(self) -> dict[str, McpServerConfig]:
        servers = self.mcp_servers()
        missing = [name for name, cfg in servers.items() if not cfg.is_configured]
        if missing:
            names = ", ".join(missing)
            raise ValueError(
                f"MCP server(s) not configured: {names}. "
                "Set GOOGLE_DOCS_MCP_* / GMAIL_MCP_* in .env or MCP_SERVERS_CONFIG."
            )
        return servers


def load_settings() -> Settings:
    """Load and validate application settings."""
    return Settings()
