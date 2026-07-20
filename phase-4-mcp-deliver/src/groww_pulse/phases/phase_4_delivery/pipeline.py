"""Phase 4 delivery pipeline."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from groww_pulse.config import DeliverySettings
from groww_pulse.models import DeliveryResult, Pulse
from groww_pulse.phases.phase_4_delivery.mcp_http import GoogleMcpHttpClient, McpToolError
from groww_pulse.phases.phase_4_delivery.render import render_document_body, render_email
from groww_pulse.phases.phase_4_delivery.state import (
    get_week_record,
    load_state,
    mark_week_delivered,
    save_state,
)
from groww_pulse.phases.phase_4_delivery.validate import scan_for_pii

logger = logging.getLogger("groww_pulse.deliver")


def _write_dry_run_artifacts(
    pulse: Pulse,
    *,
    doc_body: str,
    subject: str,
    email_body: str,
    output_dir: Path,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "pulse_document.txt").write_text(doc_body, encoding="utf-8")
    (output_dir / "pulse_email.txt").write_text(
        f"To: (configured RECIPIENT)\nSubject: {subject}\n\n{email_body}",
        encoding="utf-8",
    )
    preview = {
        "week_of": pulse.week_of.isoformat(),
        "dry_run": True,
        "document_preview": doc_body[:500],
        "email_subject": subject,
    }
    (output_dir / "delivery_preview.json").write_text(
        json.dumps(preview, indent=2),
        encoding="utf-8",
    )


def deliver_pulse(
    pulse: Pulse,
    settings: DeliverySettings,
) -> tuple[DeliveryResult, dict[str, Any]]:
    doc_body = render_document_body(pulse)
    pii_issues = scan_for_pii(doc_body)
    if pii_issues:
        raise ValueError(f"PII detected in rendered document: {pii_issues[:3]}")

    result = DeliveryResult(week_of=pulse.week_of, dry_run=settings.dry_run)
    report: dict[str, Any] = {
        "tools_discovered": [],
        "pii_scan_ok": True,
        "skipped_reason": None,
    }

    state = load_state(settings.delivery_state_path)
    prior = get_week_record(state, pulse.week_of)
    if prior.get("delivered"):
        logger.info("Week %s already delivered; returning cached artifacts", pulse.week_of)
        result.doc_id = prior.get("doc_id")
        result.doc_url = prior.get("doc_url")
        result.draft_id = prior.get("draft_id")
        report["skipped_reason"] = "already_delivered"
        return result, report

    if settings.dry_run:
        out = settings.delivery_state_path.parent
        subject, email_body = render_email(pulse, doc_url=None)
        _write_dry_run_artifacts(
            pulse,
            doc_body=doc_body,
            subject=subject,
            email_body=email_body,
            output_dir=out,
        )
        result.tools_called = ["dry_run"]
        logger.info("DRY_RUN=true — wrote preview artifacts to %s", out)
        return result, report

    if not settings.google_doc_id.strip():
        result.errors.append("GOOGLE_DOC_ID is required when DRY_RUN=false")
        return result, report

    client = GoogleMcpHttpClient(
        base_url=settings.mcp_server_base_url,
        append_tool=settings.mcp_append_tool,
        draft_tool=settings.mcp_draft_tool,
        timeout_sec=settings.mcp_request_timeout_sec,
        max_retries=settings.mcp_max_retries,
    )

    discovery = client.discover_tools()
    report["tools_discovered"] = discovery.tools
    if discovery.error:
        result.errors.append(discovery.error)
        return result, report

    doc_id = settings.google_doc_id.strip()

    try:
        doc_response = client.append_to_doc(doc_id, doc_body)
        result.tools_called.append(settings.mcp_append_tool)
        returned_id = doc_response.get("document_id") or doc_id
        result.doc_id = returned_id
        result.doc_url = client.doc_url_from_id(returned_id)

        subject, email_body = render_email(pulse, doc_url=result.doc_url)
        email_pii = scan_for_pii(email_body)
        if email_pii:
            raise ValueError(f"PII detected in email body: {email_pii[:3]}")

        draft_response = client.create_email_draft(settings.recipient, subject, email_body)
        result.tools_called.append(settings.mcp_draft_tool)
        result.draft_id = draft_response.get("draft_id")

        if not result.draft_id:
            result.errors.append("create_email_draft did not return draft_id")
            return result, report

        state = mark_week_delivered(
            state,
            week_of=pulse.week_of,
            doc_id=returned_id,
            doc_url=result.doc_url,
            draft_id=result.draft_id,
        )
        save_state(settings.delivery_state_path, state)
        logger.info("Delivery complete: doc=%s draft=%s", result.doc_url, result.draft_id)

    except (McpToolError, ValueError) as exc:
        logger.error("Delivery failed: %s", exc)
        result.errors.append(str(exc))

    return result, report
