"""Pulse validation helpers."""

from __future__ import annotations

import re
from dataclasses import dataclass

from groww_pulse.models import Pulse, PulseQuote, PulseTheme, Review

EMAIL_PATTERN = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")


@dataclass
class ValidationResult:
    ok: bool
    errors: list[str]


def review_full_text(review: Review) -> str:
    if review.title.strip():
        return f"{review.title.strip()}. {review.text}"
    return review.text


def quote_is_verbatim(quote: PulseQuote, review_lookup: dict[str, Review]) -> bool:
    review = review_lookup.get(quote.review_id)
    if review is None:
        return False
    source = review_full_text(review)
    text = quote.text
    # A quote truncated for length ends with an ellipsis; the remaining prefix
    # must still be a genuine substring of the source review.
    if text.endswith("\u2026"):
        text = text[:-1].rstrip()
    return text in source or text in review.text


def count_pulse_words(pulse: Pulse) -> int:
    parts: list[str] = []
    for theme in pulse.top_themes:
        parts.extend([theme.name, theme.one_line_summary])
    parts.extend(quote.text for quote in pulse.quotes)
    parts.extend(pulse.action_ideas)
    text = " ".join(part for part in parts if part)
    return len(re.findall(r"\b[\w'-]+\b", text))


def validate_pulse(pulse: Pulse, review_lookup: dict[str, Review]) -> ValidationResult:
    errors: list[str] = []

    if len(pulse.top_themes) != 3:
        errors.append("expected exactly 3 top_themes")
    if len(pulse.quotes) != 3:
        errors.append("expected exactly 3 quotes")
    if len(pulse.action_ideas) != 3:
        errors.append("expected exactly 3 action_ideas")

    for quote in pulse.quotes:
        if not quote_is_verbatim(quote, review_lookup):
            errors.append(f"quote not verbatim for review_id={quote.review_id}")
        if EMAIL_PATTERN.search(quote.text):
            errors.append(f"quote contains email-like text: {quote.review_id}")

    word_count = count_pulse_words(pulse)
    if word_count > 250:
        errors.append(f"word_count {word_count} exceeds 250")

    if pulse.word_count != word_count:
        errors.append("pulse.word_count mismatch")

    return ValidationResult(ok=not errors, errors=errors)
