"""Final PII scan on delivery artifacts."""

from __future__ import annotations

import re

EMAIL_PATTERN = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
PHONE_PATTERN = re.compile(r"(?<!\d)(?:\+?\d{1,3}[-.\s]?)?(?:\d{10}|\d{5}[-.\s]?\d{5})(?!\d)")


def scan_for_pii(text: str) -> list[str]:
    issues: list[str] = []
    for match in EMAIL_PATTERN.finditer(text):
        issues.append(f"email-like: {match.group()}")
    for match in PHONE_PATTERN.finditer(text):
        issues.append(f"phone-like: {match.group()}")
    return issues
