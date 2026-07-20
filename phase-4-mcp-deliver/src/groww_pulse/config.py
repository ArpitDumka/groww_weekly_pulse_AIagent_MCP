"""Phase 4 delivery configuration."""

from __future__ import annotations

from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class DeliverySettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    phase3_pulse_input: Path = Field(
        default=Path("../phase-3-theme-summarize/data/output/pulse_dashboard.json"),
        alias="PHASE3_PULSE_INPUT",
    )
    recipient: str = Field(alias="RECIPIENT")
    google_doc_id: str = Field(default="", alias="GOOGLE_DOC_ID")
    mcp_server_base_url: str = Field(
        default="http://127.0.0.1:8000",
        alias="MCP_SERVER_BASE_URL",
    )
    mcp_append_tool: str = Field(default="append_to_doc", alias="MCP_APPEND_TOOL")
    mcp_draft_tool: str = Field(default="create_email_draft", alias="MCP_DRAFT_TOOL")
    dry_run: bool = Field(default=True, alias="DRY_RUN")
    delivery_state_path: Path = Field(
        default=Path("data/output/delivery_state.json"),
        alias="DELIVERY_STATE_PATH",
    )
    mcp_request_timeout_sec: float = Field(default=60.0, alias="MCP_REQUEST_TIMEOUT_SEC")
    mcp_max_retries: int = Field(default=2, ge=0, le=5, alias="MCP_MAX_RETRIES")

    @field_validator("recipient")
    @classmethod
    def recipient_not_empty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("RECIPIENT must not be empty")
        if "@" not in value:
            raise ValueError("RECIPIENT must look like an email address")
        return value.strip()

    @field_validator("mcp_server_base_url")
    @classmethod
    def strip_trailing_slash(cls, value: str) -> str:
        return value.rstrip("/")


def load_settings() -> DeliverySettings:
    return DeliverySettings()
