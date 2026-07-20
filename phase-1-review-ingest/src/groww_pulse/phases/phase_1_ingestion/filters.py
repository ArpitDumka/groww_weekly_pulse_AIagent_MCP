"""Post-parse normalization filters: word count, emoji, English-only."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass

from groww_pulse.models import Review, ReviewSource

logger = logging.getLogger("groww_pulse.ingest")

WORD_PATTERN = re.compile(r"\b[\w'-]+\b", flags=re.UNICODE)
EMOJI_PATTERN = re.compile(
    "["
    "\U0001F1E0-\U0001F1FF"
    "\U0001F300-\U0001F5FF"
    "\U0001F600-\U0001F64F"
    "\U0001F680-\U0001F6FF"
    "\U0001F700-\U0001F77F"
    "\U0001F780-\U0001F7FF"
    "\U0001F800-\U0001F8FF"
    "\U0001F900-\U0001F9FF"
    "\U0001FA00-\U0001FA6F"
    "\U0001FA70-\U0001FAFF"
    "\U00002600-\U000026FF"
    "\U00002700-\U000027BF"
    "\U0000FE00-\U0000FE0F"
    "\U0001F3FB-\U0001F3FF"
    "]+",
    flags=re.UNICODE,
)
NON_ENGLISH_SCRIPTS = re.compile(
    r"[\u0900-\u097F\u0980-\u09FF\u0A00-\u0A7F\u0A80-\u0AFF\u0B00-\u0B7F"
    r"\u0B80-\u0BFF\u0C00-\u0C7F\u0C80-\u0CFF\u0D00-\u0D7F\u0590-\u05FF"
    r"\u0600-\u06FF\u4E00-\u9FFF\u3040-\u30FF\uAC00-\uD7AF]",
)


@dataclass
class NormalizationFilterSettings:
    min_word_count: int = 6
    english_only: bool = True
    reject_emoji: bool = True


@dataclass
class FilterReport:
    skipped_too_short: int = 0
    skipped_has_emoji: int = 0
    skipped_non_english: int = 0

    @property
    def total_skipped(self) -> int:
        return self.skipped_too_short + self.skipped_has_emoji + self.skipped_non_english


def review_word_count(review: Review) -> int:
    combined = f"{review.title} {review.text}".strip()
    return len(WORD_PATTERN.findall(combined))


def review_has_emoji(review: Review) -> bool:
    combined = f"{review.title} {review.text}"
    return bool(EMOJI_PATTERN.search(combined))


def is_english_review(review: Review) -> bool:
    combined = f"{review.title} {review.text}".strip()
    if not combined:
        return False

    if NON_ENGLISH_SCRIPTS.search(combined):
        return False

    if review.locale and review.source == ReviewSource.PLAY_STORE:
        locale_code = review.locale.lower().replace("_", "-").split("-")[0]
        if locale_code not in {"en", "eng"}:
            return False

    try:
        from langdetect import LangDetectException, detect

        return detect(combined) == "en"
    except LangDetectException:
        logger.debug("Language detection failed for review %s", review.id)
        return False


def filter_reviews(
    reviews: list[Review],
    settings: NormalizationFilterSettings,
) -> tuple[list[Review], FilterReport]:
    report = FilterReport()
    kept: list[Review] = []

    for review in reviews:
        if settings.min_word_count > 0 and review_word_count(review) < settings.min_word_count:
            report.skipped_too_short += 1
            continue
        if settings.reject_emoji and review_has_emoji(review):
            report.skipped_has_emoji += 1
            continue
        if settings.english_only and not is_english_review(review):
            report.skipped_non_english += 1
            continue
        kept.append(review)

    if report.total_skipped:
        logger.info(
            "Normalization filters: kept=%s skipped_short=%s skipped_emoji=%s skipped_non_english=%s",
            len(kept),
            report.skipped_too_short,
            report.skipped_has_emoji,
            report.skipped_non_english,
        )

    return kept, report
