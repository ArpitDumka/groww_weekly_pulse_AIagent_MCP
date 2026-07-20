"""Deduplicate normalized reviews by stable id."""

from __future__ import annotations

from groww_pulse.models import Review


def dedupe_reviews(reviews: list[Review]) -> tuple[list[Review], int]:
    seen: dict[str, Review] = {}
    duplicates = 0
    for review in reviews:
        if review.id in seen:
            duplicates += 1
            continue
        seen[review.id] = review
    return list(seen.values()), duplicates
