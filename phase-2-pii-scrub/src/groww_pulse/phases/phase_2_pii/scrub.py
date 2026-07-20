"""PII scrubbing pipeline."""

from __future__ import annotations

import logging
from collections import Counter
from dataclasses import dataclass, field
from typing import Iterable

from groww_pulse.models import Review
from groww_pulse.phases.phase_2_pii.patterns import (
    PII_PATTERNS,
    PiiCategory,
    protect_versions,
    restore_versions,
)

logger = logging.getLogger("groww_pulse.pii")


@dataclass
class RedactionReport:
    reviews_processed: int = 0
    fields_scrubbed: int = 0
    by_category: dict[str, int] = field(default_factory=dict)
    ambiguous_redactions: int = 0

    @property
    def total_redactions(self) -> int:
        return sum(self.by_category.values())

    def log(self) -> None:
        logger.info(
            "PII scrub complete: reviews=%s fields=%s total_redactions=%s by_category=%s ambiguous=%s",
            self.reviews_processed,
            self.fields_scrubbed,
            self.total_redactions,
            self.by_category,
            self.ambiguous_redactions,
        )


@dataclass(frozen=True)
class ScrubbedCorpus:
    """Hard-gate wrapper: only produced by scrub_reviews()."""

    reviews: tuple[Review, ...]
    report: RedactionReport


def scrub_text(text: str, *, redaction_token: str = "[REDACTED]") -> tuple[str, Counter[PiiCategory]]:
    if not text:
        return text, Counter()

    protected, placeholders = protect_versions(text)
    counts: Counter[PiiCategory] = Counter()

    for pii_pattern in PII_PATTERNS:
        protected, replacements = pii_pattern.pattern.subn(redaction_token, protected)
        if replacements:
            counts[pii_pattern.category] += replacements

    restored = restore_versions(protected, placeholders)
    return restored, counts


def scrub_review(review: Review, *, redaction_token: str = "[REDACTED]") -> tuple[Review, Counter[PiiCategory]]:
    title, title_counts = scrub_text(review.title, redaction_token=redaction_token)
    text, text_counts = scrub_text(review.text, redaction_token=redaction_token)
    combined = title_counts + text_counts

    scrubbed = review.model_copy(update={"title": title, "text": text})
    return scrubbed, combined


def scrub_reviews(
    reviews: Iterable[Review],
    *,
    redaction_token: str = "[REDACTED]",
) -> ScrubbedCorpus:
    report = RedactionReport()
    scrubbed_reviews: list[Review] = []

    for review in reviews:
        scrubbed, counts = scrub_review(review, redaction_token=redaction_token)
        scrubbed_reviews.append(scrubbed)
        report.reviews_processed += 1

        if counts:
            report.fields_scrubbed += 1
            for category, count in counts.items():
                report.by_category[category.value] = report.by_category.get(category.value, 0) + count
                if category == PiiCategory.AMBIGUOUS:
                    report.ambiguous_redactions += count

    report.log()
    return ScrubbedCorpus(reviews=tuple(scrubbed_reviews), report=report)
