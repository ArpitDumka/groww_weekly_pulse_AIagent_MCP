"""Render Pulse into Google Doc and Gmail draft bodies."""

from __future__ import annotations

from groww_pulse.models import Pulse


def render_document_body(pulse: Pulse) -> str:
    lines = [
        f"Groww Weekly Review Pulse — Week of {pulse.week_of.isoformat()}",
        "",
        f"Reviews analyzed: {pulse.meta.review_count:,}",
        f"Word count: {pulse.word_count} / 250",
        "",
    ]

    split = pulse.meta.source_split
    if split:
        parts = ", ".join(f"{k}: {v:,}" for k, v in split.items())
        lines.extend([f"Source split: {parts}", ""])

    for index, theme in enumerate(pulse.top_themes, start=1):
        quote = pulse.quotes[index - 1] if index - 1 < len(pulse.quotes) else None
        action = pulse.action_ideas[index - 1] if index - 1 < len(pulse.action_ideas) else ""

        lines.append(f"Theme {index}: {theme.name}")
        lines.append(theme.one_line_summary)
        if quote:
            lines.append(f'Quote: "{quote.text}"')
            lines.append(f"(review_id: {quote.review_id})")
        if action:
            lines.append(f"Action: {action}")
        lines.append("")

    return "\n".join(lines).strip()


def render_email(pulse: Pulse, *, doc_url: str | None = None) -> tuple[str, str]:
    subject = f"Groww Weekly Review Pulse — {pulse.week_of.isoformat()}"
    body_lines = [
        "Weekly review pulse summary",
        "",
        render_document_body(pulse),
    ]
    if doc_url:
        body_lines.extend(["", f"Google Doc: {doc_url}"])
    return subject, "\n".join(body_lines).strip()
