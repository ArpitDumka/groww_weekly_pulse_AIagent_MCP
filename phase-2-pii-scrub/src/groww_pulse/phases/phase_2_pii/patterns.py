"""Deterministic PII detection patterns (architecture §3.2, ADR-002)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum


class PiiCategory(str, Enum):
    EMAIL = "email"
    PHONE = "phone"
    HANDLE = "handle"
    ACCOUNT_ID = "account_id"
    DEVICE_ID = "device_id"
    AMBIGUOUS = "ambiguous"


@dataclass(frozen=True)
class PiiPattern:
    category: PiiCategory
    pattern: re.Pattern[str]


VERSION_PATTERN = re.compile(
    r"(?<![\d.])(?:v|version\s+)(\d+\.\d+(?:\.\d+)?)(?![\d.])",
    re.IGNORECASE,
)
BARE_VERSION_PATTERN = re.compile(
    r"(?<![\d.])(\d+\.\d+\.\d+)(?![\d.])",
)

PII_PATTERNS: tuple[PiiPattern, ...] = (
    PiiPattern(
        PiiCategory.EMAIL,
        re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", re.IGNORECASE),
    ),
    PiiPattern(
        PiiCategory.PHONE,
        re.compile(
            r"(?<!\d)(?:\+?\d{1,3}[\s.-]?)?(?:\(\d{2,4}\)|\d{2,4})[\s.-]?\d{3,4}[\s.-]?\d{3,4}(?!\d)",
        ),
    ),
    PiiPattern(
        PiiCategory.PHONE,
        re.compile(r"(?<!\d)\+91[\s.-]?\d{10}(?!\d)"),
    ),
    PiiPattern(
        PiiCategory.PHONE,
        re.compile(r"(?<!\d)[6-9]\d{9}(?!\d)"),
    ),
    PiiPattern(
        PiiCategory.DEVICE_ID,
        re.compile(
            r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b",
        ),
    ),
    PiiPattern(
        PiiCategory.HANDLE,
        re.compile(r"@[a-zA-Z0-9_]{2,30}\b"),
    ),
    PiiPattern(
        PiiCategory.HANDLE,
        re.compile(
            r"(?i)\b(?:my\s+(?:username|user\s*name|handle|id)\s*(?:is|:)\s*)[\w@.-]+",
        ),
    ),
    PiiPattern(
        PiiCategory.ACCOUNT_ID,
        re.compile(
            r"(?i)\b(?:order|acct|account|ref|reference|ticket|txn|transaction|folio|pan|aadhaar|aadhar)"
            r"[\s#:=-]*[A-Z0-9-]{6,}\b",
        ),
    ),
    PiiPattern(
        PiiCategory.ACCOUNT_ID,
        re.compile(r"(?i)\b[A-Z]{2,5}[-_]?\d{6,}\b"),
    ),
    PiiPattern(
        PiiCategory.ACCOUNT_ID,
        re.compile(r"(?<!\d)\d{8,}(?!\d)"),
    ),
    PiiPattern(
        PiiCategory.AMBIGUOUS,
        re.compile(
            r"(?<![@\w])"
            r"(?=[a-zA-Z0-9_-]*[a-zA-Z])"
            r"(?=[a-zA-Z0-9_-]*\d)"
            r"[a-zA-Z0-9_-]{10,}"
            r"(?![@\w])",
        ),
    ),
)

LEAK_PATTERNS: tuple[PiiPattern, ...] = PII_PATTERNS


def protect_versions(text: str) -> tuple[str, dict[str, str]]:
    placeholders: dict[str, str] = {}

    def _replace(match: re.Match[str]) -> str:
        key = f"__VER_{len(placeholders)}__"
        placeholders[key] = match.group(0)
        return key

    protected = VERSION_PATTERN.sub(_replace, text)
    protected = BARE_VERSION_PATTERN.sub(_replace, protected)
    return protected, placeholders


def restore_versions(text: str, placeholders: dict[str, str]) -> str:
    restored = text
    for key, original in placeholders.items():
        restored = restored.replace(key, original)
    return restored


def find_pii_matches(text: str) -> list[tuple[PiiCategory, str]]:
    """Return category + matched substring for audit/leak detection."""
    if not text:
        return []

    protected, placeholders = protect_versions(text)
    matches: list[tuple[PiiCategory, str]] = []

    for pii_pattern in PII_PATTERNS:
        for match in pii_pattern.pattern.finditer(protected):
            snippet = match.group(0)
            if snippet.startswith("__VER_") and snippet.endswith("__"):
                continue
            matches.append((pii_pattern.category, snippet))

    _ = placeholders
    return matches
