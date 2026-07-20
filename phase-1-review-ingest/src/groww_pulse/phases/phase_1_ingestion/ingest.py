"""Ingestion pipeline orchestration."""

from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from groww_pulse.models import Review, ReviewSource
from groww_pulse.phases.phase_1_ingestion.dedupe import dedupe_reviews
from groww_pulse.phases.phase_1_ingestion.filters import NormalizationFilterSettings, filter_reviews
from groww_pulse.phases.phase_1_ingestion.parsers import parse_app_store_csv, parse_play_store_csv

logger = logging.getLogger("groww_pulse.ingest")


@dataclass
class IngestionReport:
    total_rows: int = 0
    parsed: int = 0
    skipped_malformed: int = 0
    skipped_empty: int = 0
    skipped_out_of_window: int = 0
    skipped_too_short: int = 0
    skipped_has_emoji: int = 0
    skipped_non_english: int = 0
    deduped: int = 0
    capped: int = 0
    final_count: int = 0
    by_source: dict[str, int] = field(default_factory=dict)
    sources: list[str] = field(default_factory=list)

    def log(self) -> None:
        logger.info(
            "Ingestion complete: total_rows=%s parsed=%s malformed=%s empty=%s "
            "skipped_short=%s skipped_emoji=%s skipped_non_english=%s "
            "deduped=%s capped=%s final=%s by_source=%s",
            self.total_rows,
            self.parsed,
            self.skipped_malformed,
            self.skipped_empty,
            self.skipped_too_short,
            self.skipped_has_emoji,
            self.skipped_non_english,
            self.deduped,
            self.capped,
            self.final_count,
            self.by_source,
        )


def _cap_per_source(reviews: list[Review], limit_per_source: int | None) -> tuple[list[Review], int]:
    if limit_per_source is None:
        return reviews, 0

    grouped: dict[ReviewSource, list[Review]] = defaultdict(list)
    for review in reviews:
        grouped[review.source].append(review)

    kept: list[Review] = []
    capped = 0
    for source, items in grouped.items():
        items.sort(key=lambda r: (r.date, r.id), reverse=True)
        selected = items[:limit_per_source]
        capped += max(0, len(items) - len(selected))
        kept.extend(selected)

    kept.sort(key=lambda r: (r.date, r.source.value, r.id), reverse=True)
    return kept, capped


def ingest_reviews(
    *,
    app_store_path: Path | None = None,
    play_store_path: Path | None = None,
    limit_per_source: int | None = 20_000,
    filters: NormalizationFilterSettings | None = None,
) -> tuple[list[Review], IngestionReport]:
    """Parse, normalize, filter, dedupe, and cap reviews from public store exports."""
    if app_store_path is None and play_store_path is None:
        raise ValueError("provide at least one export path")

    filter_settings = filters or NormalizationFilterSettings()
    report = IngestionReport()
    all_reviews: list[Review] = []

    if app_store_path is not None:
        if not app_store_path.is_file():
            raise FileNotFoundError(app_store_path)
        reviews, stats = parse_app_store_csv(app_store_path)
        all_reviews.extend(reviews)
        report.sources.append("app_store")
        report.total_rows += stats.total_rows
        report.parsed += stats.parsed
        report.skipped_malformed += stats.skipped_malformed
        report.skipped_empty += stats.skipped_empty

    if play_store_path is not None:
        if not play_store_path.is_file():
            raise FileNotFoundError(play_store_path)
        reviews, stats = parse_play_store_csv(play_store_path)
        all_reviews.extend(reviews)
        report.sources.append("play_store")
        report.total_rows += stats.total_rows
        report.parsed += stats.parsed
        report.skipped_malformed += stats.skipped_malformed
        report.skipped_empty += stats.skipped_empty

    filtered, filter_report = filter_reviews(all_reviews, filter_settings)
    report.skipped_too_short = filter_report.skipped_too_short
    report.skipped_has_emoji = filter_report.skipped_has_emoji
    report.skipped_non_english = filter_report.skipped_non_english

    deduped, duplicate_count = dedupe_reviews(filtered)
    report.deduped = duplicate_count

    final, capped = _cap_per_source(deduped, limit_per_source)
    report.capped = capped
    report.final_count = len(final)
    report.by_source = {
        source.value: sum(1 for review in final if review.source == source)
        for source in ReviewSource
        if any(review.source == source for review in final)
    }

    report.log()
    return final, report
