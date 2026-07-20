"""App Store Connect review export parser."""

from __future__ import annotations

import logging
from pathlib import Path

from groww_pulse.models import Review, ReviewSource
from groww_pulse.phases.phase_1_ingestion.id_utils import make_review_id
from groww_pulse.phases.phase_1_ingestion.parsers.common import (
    ParseStats,
    RawReviewRow,
    parse_date,
    parse_rating,
    pick_field,
    read_csv_rows,
)

logger = logging.getLogger("groww_pulse.ingest")

_RATING_ALIASES = ["rating", "star rating"]
_TITLE_ALIASES = ["title", "review title"]
_TEXT_ALIASES = ["review", "review text", "body"]
_DATE_ALIASES = ["date", "review date", "created"]
_VERSION_ALIASES = ["app version", "version"]
_LOCALE_ALIASES = ["territory", "country code", "country"]


def _row_to_raw(row: dict[str, str]) -> RawReviewRow:
    rating_raw = pick_field(row, _RATING_ALIASES)
    text = pick_field(row, _TEXT_ALIASES)
    date_raw = pick_field(row, _DATE_ALIASES)

    if not rating_raw or not text or not date_raw:
        raise ValueError("missing required fields")

    return RawReviewRow(
        rating=parse_rating(rating_raw),
        title=pick_field(row, _TITLE_ALIASES),
        text=text,
        review_date=parse_date(date_raw),
        app_version=pick_field(row, _VERSION_ALIASES) or None,
        locale=pick_field(row, _LOCALE_ALIASES) or None,
    )


def _to_review(raw: RawReviewRow) -> Review:
    return Review(
        id=make_review_id(ReviewSource.APP_STORE, raw.text, raw.review_date),
        source=ReviewSource.APP_STORE,
        rating=raw.rating,
        title=raw.title,
        text=raw.text,
        date=raw.review_date,
        app_version=raw.app_version,
        locale=raw.locale,
    )


def parse_app_store_csv(path: Path) -> tuple[list[Review], ParseStats]:
    stats = ParseStats()
    reviews: list[Review] = []

    _, rows = read_csv_rows(path)
    stats.total_rows = len(rows)

    for index, row in enumerate(rows, start=2):
        try:
            raw = _row_to_raw(row)
        except ValueError as exc:
            message = str(exc).lower()
            if "missing required" in message or "empty" in message:
                stats.skipped_empty += 1
                logger.debug("App Store row %s skipped (empty): %s", index, exc)
            else:
                stats.skipped_malformed += 1
                logger.debug("App Store row %s skipped (malformed): %s", index, exc)
            continue

        try:
            reviews.append(_to_review(raw))
            stats.parsed += 1
        except ValueError as exc:
            stats.skipped_malformed += 1
            logger.debug("App Store row %s invalid review: %s", index, exc)

    return reviews, stats
