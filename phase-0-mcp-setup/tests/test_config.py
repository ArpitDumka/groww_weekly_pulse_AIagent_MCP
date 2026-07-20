"""Config loading tests."""

import os
from pathlib import Path

import pytest

from groww_pulse.config import Settings


def test_settings_load_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RECIPIENT", "pulse@example.com")
    monkeypatch.setenv("WINDOW_WEEKS", "10")
    monkeypatch.setenv("MAX_THEMES", "5")
    monkeypatch.setenv("TOP_THEMES", "3")
    monkeypatch.setenv("DRY_RUN", "true")

    settings = Settings(_env_file=None)

    assert settings.recipient == "pulse@example.com"
    assert settings.window_weeks == 10
    assert settings.max_themes == 5
    assert settings.dry_run is True


def test_top_themes_must_not_exceed_max(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RECIPIENT", "pulse@example.com")
    monkeypatch.setenv("TOP_THEMES", "6")
    monkeypatch.setenv("MAX_THEMES", "5")

    with pytest.raises(ValueError, match="TOP_THEMES"):
        Settings(_env_file=None)


def test_mcp_servers_from_json(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RECIPIENT", "pulse@example.com")
    config_path = tmp_path / "mcp.json"
    config_path.write_text(
        """
        {
          "servers": {
            "google_docs": {
              "command": "echo",
              "args": ["docs"],
              "expected_tools": ["create_document"],
              "create_tool": "create_document"
            },
            "gmail": {
              "command": "echo",
              "args": ["mail"],
              "expected_tools": ["create_draft"],
              "create_tool": "create_draft"
            }
          }
        }
        """,
        encoding="utf-8",
    )

    settings = Settings(RECIPIENT="pulse@example.com", MCP_SERVERS_CONFIG=config_path)
    servers = settings.mcp_servers()

    assert servers["google_docs"].command == "echo"
    assert servers["google_docs"].args == ["docs"]
    assert servers["gmail"].create_tool == "create_draft"
