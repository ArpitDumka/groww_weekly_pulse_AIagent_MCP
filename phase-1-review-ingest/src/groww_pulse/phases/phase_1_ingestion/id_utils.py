"""Stable identity-free review IDs (ADR-009)."""

from __future__ import annotations

import hashlib
import re
from datetime import date

from groww_pulse.models import ReviewSource


def normalize_text(text: str) -> str:
    collapsed = re.sub(r"\s+", " ", text.strip().lower())
    return collapsed


def make_review_id(source: ReviewSource, text: str, review_date: date) -> str:
    payload = f"{source.value}|{normalize_text(text)}|{review_date.isoformat()}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]
