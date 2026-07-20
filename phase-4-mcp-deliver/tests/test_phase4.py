"""Phase 4 delivery tests."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from groww_pulse.config import DeliverySettings
from groww_pulse.models import Pulse, PulseMeta, PulseQuote, PulseTheme
from groww_pulse.phases.phase_4_delivery.mcp_http import GoogleMcpHttpClient
from groww_pulse.phases.phase_4_delivery.pipeline import deliver_pulse
from groww_pulse.phases.phase_4_delivery.render import render_document_body, render_email
from groww_pulse.phases.phase_4_delivery.validate import scan_for_pii


@pytest.fixture
def sample_pulse() -> Pulse:
    return Pulse(
        week_of=date(2026, 6, 12),
        top_themes=[
            PulseTheme(name="Support", one_line_summary="Long wait times"),
            PulseTheme(name="Technical", one_line_summary="App glitches"),
            PulseTheme(name="Fees", one_line_summary="High charges"),
        ],
        quotes=[
            PulseQuote(review_id="a1", text="worst support ever", theme_name="Support"),
            PulseQuote(review_id="b2", text="app keeps crashing", theme_name="Technical"),
            PulseQuote(review_id="c3", text="fees too high", theme_name="Fees"),
        ],
        action_ideas=["Fix support", "Fix crashes", "Review fees"],
        word_count=40,
        meta=PulseMeta(review_count=100, source_split={"play_store": 90, "app_store": 10}),
    )


def test_render_document_contains_themes(sample_pulse: Pulse) -> None:
    body = render_document_body(sample_pulse)
    assert "Support" in body
    assert "worst support ever" in body
    assert "Groww Weekly Review Pulse" in body


def test_render_email_includes_doc_link(sample_pulse: Pulse) -> None:
    subject, body = render_email(sample_pulse, doc_url="https://docs.google.com/document/d/abc/edit")
    assert "2026-06-12" in subject
    assert "abc" in body


def test_pii_scan_clean(sample_pulse: Pulse) -> None:
    assert scan_for_pii(render_document_body(sample_pulse)) == []


def test_dry_run_writes_artifacts(
    sample_pulse: Pulse, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DRY_RUN", "true")
    monkeypatch.setenv("DELIVERY_STATE_PATH", str(tmp_path / "state.json"))
    monkeypatch.setenv("RECIPIENT", "me@example.com")
    settings = DeliverySettings()
    result, _ = deliver_pulse(sample_pulse, settings)
    assert result.dry_run is True
    assert (tmp_path / "pulse_document.txt").is_file()
    assert (tmp_path / "pulse_email.txt").is_file()


def test_live_delivery_mock(
    httpx_mock,
    sample_pulse: Pulse,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DRY_RUN", "false")
    monkeypatch.setenv("DELIVERY_STATE_PATH", str(tmp_path / "state.json"))
    monkeypatch.setenv("RECIPIENT", "me@example.com")
    monkeypatch.setenv("GOOGLE_DOC_ID", "doc123")
    monkeypatch.setenv("MCP_SERVER_BASE_URL", "http://testserver")
    settings = DeliverySettings()

    httpx_mock.add_response(url="http://testserver/openapi.json", json={"paths": {"/append_to_doc": {}, "/create_email_draft": {}}})
    httpx_mock.add_response(
        url="http://testserver/append_to_doc",
        method="POST",
        json={"status": "success", "document_id": "doc123", "message": "ok"},
    )
    httpx_mock.add_response(
        url="http://testserver/create_email_draft",
        method="POST",
        json={"status": "success", "draft_id": "draft456", "message": "ok"},
    )

    result, report = deliver_pulse(sample_pulse, settings)
    assert result.doc_url == "https://docs.google.com/document/d/doc123/edit"
    assert result.draft_id == "draft456"
    assert result.ok
    assert settings.mcp_append_tool in result.tools_called


def test_doc_url_helper() -> None:
    assert GoogleMcpHttpClient.doc_url_from_id("abc") == "https://docs.google.com/document/d/abc/edit"
