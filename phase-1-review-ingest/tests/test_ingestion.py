"""Phase 1 ingestion tests."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from groww_pulse.models import Review, ReviewSource
from groww_pulse.phases.phase_1_ingestion.filters import (
    NormalizationFilterSettings,
    is_english_review,
    review_has_emoji,
    review_word_count,
)
from groww_pulse.phases.phase_1_ingestion.id_utils import make_review_id
from groww_pulse.phases.phase_1_ingestion.ingest import ingest_reviews
from groww_pulse.phases.phase_1_ingestion.window import is_in_window

FIXTURES = Path(__file__).resolve().parent.parent / "data" / "fixtures"
AS_OF = date(2026, 6, 4)


@pytest.fixture
def app_store_path() -> Path:
    return FIXTURES / "app_store_reviews.csv"


@pytest.fixture
def play_store_path() -> Path:
    return FIXTURES / "play_store_reviews.csv"


def test_parse_both_sources(app_store_path: Path, play_store_path: Path) -> None:
    reviews, report = ingest_reviews(
        app_store_path=app_store_path,
        play_store_path=play_store_path,
    )

    sources = {review.source for review in reviews}
    assert ReviewSource.APP_STORE in sources
    assert ReviewSource.PLAY_STORE in sources
    assert report.final_count == len(reviews)
    assert report.skipped_out_of_window == 0


def test_schema_conformance(app_store_path: Path, play_store_path: Path) -> None:
    reviews, _ = ingest_reviews(
        app_store_path=app_store_path,
        play_store_path=play_store_path,
    )

    for review in reviews:
        validated = Review.model_validate(review.model_dump())
        assert validated.id
        assert 1 <= validated.rating <= 5
        assert validated.text


def test_no_date_window_by_default(app_store_path: Path, play_store_path: Path) -> None:
    reviews, report = ingest_reviews(
        app_store_path=app_store_path,
        play_store_path=play_store_path,
    )

    assert report.skipped_out_of_window == 0
    assert any(review.date < date(2026, 1, 1) for review in reviews)


def test_optional_date_window_module() -> None:
    assert is_in_window(date(2026, 5, 1), AS_OF, 12) is True
    assert is_in_window(date(2025, 1, 1), AS_OF, 12) is False


def test_dedup(app_store_path: Path, play_store_path: Path) -> None:
    _, report = ingest_reviews(
        app_store_path=app_store_path,
        play_store_path=play_store_path,
    )

    assert report.deduped >= 1


def test_stable_ids(app_store_path: Path) -> None:
    first, _ = ingest_reviews(app_store_path=app_store_path)
    second, _ = ingest_reviews(app_store_path=app_store_path)

    assert [review.id for review in first] == [review.id for review in second]


def test_identity_free_ids() -> None:
    review_date = date(2026, 5, 10)
    review_id = make_review_id(ReviewSource.APP_STORE, "Sample review text", review_date)
    assert len(review_id) == 16
    assert "@" not in review_id


def test_malformed_rows_skipped(app_store_path: Path, play_store_path: Path) -> None:
    _, report = ingest_reviews(
        app_store_path=app_store_path,
        play_store_path=play_store_path,
    )

    assert report.skipped_malformed >= 2
    assert report.skipped_empty >= 1


def test_expected_fixture_count(app_store_path: Path, play_store_path: Path) -> None:
    reviews, report = ingest_reviews(
        app_store_path=app_store_path,
        play_store_path=play_store_path,
    )

    assert report.final_count == 10
    assert len(reviews) == 10


def test_normalization_filters_skip_short_emoji_and_non_english(
    app_store_path: Path,
    play_store_path: Path,
) -> None:
    _, report = ingest_reviews(
        app_store_path=app_store_path,
        play_store_path=play_store_path,
    )

    assert report.skipped_too_short >= 2
    assert report.skipped_has_emoji >= 2
    assert report.skipped_non_english >= 2


def test_kept_reviews_meet_word_emoji_and_english_rules(
    app_store_path: Path,
    play_store_path: Path,
) -> None:
    reviews, _ = ingest_reviews(
        app_store_path=app_store_path,
        play_store_path=play_store_path,
    )

    for review in reviews:
        assert review_word_count(review) >= 6
        assert not review_has_emoji(review)
        assert is_english_review(review)


def test_filters_can_be_disabled(app_store_path: Path, play_store_path: Path) -> None:
    _, report = ingest_reviews(
        app_store_path=app_store_path,
        play_store_path=play_store_path,
        filters=NormalizationFilterSettings(
            min_word_count=0,
            english_only=False,
            reject_emoji=False,
        ),
    )

    assert report.skipped_too_short == 0
    assert report.skipped_has_emoji == 0
    assert report.skipped_non_english == 0
