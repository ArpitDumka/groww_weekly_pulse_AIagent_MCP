"""Phase 0 config-only smoke test."""

import pytest

from groww_pulse.phases.phase_0_foundations.hello_mcp import async_main


@pytest.mark.asyncio
async def test_hello_mcp_config_only(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RECIPIENT", "pulse@example.com")
    monkeypatch.delenv("MCP_SERVERS_CONFIG", raising=False)

    code = await async_main(["--config-only"])
    assert code == 0
