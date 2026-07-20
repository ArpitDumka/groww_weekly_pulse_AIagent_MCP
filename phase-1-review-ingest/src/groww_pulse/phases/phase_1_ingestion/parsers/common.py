"""CSV parsing helpers shared by store-specific parsers."""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Iterable


@dataclass
class ParseStats:
    total_rows: int = 0
    parsed: int = 0
    skipped_malformed: int = 0
    skipped_empty: int = 0

    def merge(self, other: ParseStats) -> None:
        self.total_rows += other.total_rows
        self.parsed += other.parsed
        self.skipped_malformed += other.skipped_malformed
        self.skipped_empty += other.skipped_empty


@dataclass
class RawReviewRow:
    rating: int
    title: str
    text: str
    review_date: date
    app_version: str | None = None
    locale: str | None = None


def read_csv_rows(path: Path) -> tuple[list[str], Iterable[dict[str, str]]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise ValueError(f"CSV has no header row: {path}")
        rows = list(reader)
    return list(reader.fieldnames), rows


def pick_field(row: dict[str, str], aliases: list[str]) -> str:
    normalized = {key.strip().lower(): value for key, value in row.items() if key}
    for alias in aliases:
        value = normalized.get(alias.lower())
        if value is not None and value.strip():
            return value.strip()
    return ""


def parse_rating(raw: str) -> int:
    value = int(float(raw.strip()))
    if value < 1 or value > 5:
        raise ValueError(f"rating out of range: {value}")
    return value


def parse_date(raw: str) -> date:
    raw = raw.strip()
    formats = (
        "%Y-%m-%d",
        "%m/%d/%Y",
        "%d/%m/%Y",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S",
        "%b %d, %Y",
        "%B %d, %Y",
    )
    for fmt in formats:
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    # Play Store sometimes uses "2026-05-15 14:30:00 UTC"
    if " UTC" in raw:
        return parse_date(raw.replace(" UTC", ""))
    raise ValueError(f"unrecognized date format: {raw!r}")
