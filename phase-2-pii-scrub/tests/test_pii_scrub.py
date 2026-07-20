"""Phase 2 PII scrubbing tests (eval.md)."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from groww_pulse.models import Review, ReviewSource
from groww_pulse.phases.phase_2_pii.gate import (
    ScrubbingRequiredError,
    require_scrubbed_before_artifact_write,
    require_scrubbed_before_llm,
    simulate_llm_call,
)
from groww_pulse.phases.phase_2_pii.patterns import PiiCategory, find_pii_matches
from groww_pulse.phases.phase_2_pii.scrub import scrub_reviews, scrub_text

FIXTURES = Path(__file__).resolve().parent.parent / "data" / "fixtures"
PII_FIXTURE = FIXTURES / "pii_reviews.json"


def _load_fixture() -> tuple[list[Review], list[str], list[str]]:
    payload = json.loads(PII_FIXTURE.read_text(encoding="utf-8"))
    reviews = [Review.model_validate(item) for item in payload["reviews"]]
    return reviews, payload["must_not_contain"], payload["must_preserve"]


def _sample_review(**overrides: object) -> Review:
    base = {
        "id": "sample001",
        "source": ReviewSource.APP_STORE,
        "rating": 3,
        "title": "",
        "text": "Sample review",
        "date": date(2026, 5, 1),
    }
    base.update(overrides)
    return Review.model_validate(base)


@pytest.fixture
def pii_fixture() -> tuple[list[Review], list[str], list[str]]:
    return _load_fixture()


def test_email_removal() -> None:
    review = _sample_review(text="Reach me at alice.test@company.co.in please")
    corpus = scrub_reviews([review])
    assert "alice.test@company.co.in" not in corpus.reviews[0].text
    assert corpus.report.by_category.get(PiiCategory.EMAIL.value, 0) >= 1


def test_phone_removal_intl_and_local() -> None:
    review = _sample_review(
        text="Call +1 (415) 555-0199 or 9876543210 for support",
    )
    corpus = scrub_reviews([review])
    text = corpus.reviews[0].text
    assert "9876543210" not in text
    assert "555-0199" not in text
    assert corpus.report.by_category.get(PiiCategory.PHONE.value, 0) >= 1


def test_handle_and_username_removal() -> None:
    review = _sample_review(
        title="@angry_user",
        text="My username is trader007 and @groww ignored me",
    )
    corpus = scrub_reviews([review])
    scrubbed = corpus.reviews[0]
    assert "@angry_user" not in scrubbed.title
    assert "trader007" not in scrubbed.text
    assert "@groww" not in scrubbed.text
    assert corpus.report.by_category.get(PiiCategory.HANDLE.value, 0) >= 1


def test_account_and_device_id_removal() -> None:
    review = _sample_review(
        text="Ticket REF-ABC123456789 and uuid 550e8400-e29b-41d4-a716-446655440000",
    )
    corpus = scrub_reviews([review])
    text = corpus.reviews[0].text
    assert "REF-ABC123456789" not in text
    assert "550e8400-e29b-41d4-a716-446655440000" not in text


def test_ambiguous_tokens_redacted() -> None:
    review = _sample_review(text="Suspicious token abc12DEF34ghi56 in notes")
    corpus = scrub_reviews([review])
    assert "abc12DEF34ghi56" not in corpus.reviews[0].text
    assert corpus.report.ambiguous_redactions >= 1


def test_hard_gate_blocks_unscrubbed() -> None:
    review = _sample_review(text="Plain review")
    with pytest.raises(ScrubbingRequiredError):
        require_scrubbed_before_llm([review])

    with pytest.raises(ScrubbingRequiredError):
        require_scrubbed_before_artifact_write([review])


def test_hard_gate_allows_scrubbed_corpus() -> None:
    corpus = scrub_reviews([_sample_review(text="Plain review")])
    require_scrubbed_before_llm(corpus)
    require_scrubbed_before_artifact_write(corpus)
    assert simulate_llm_call(corpus) == "ok:1"


def test_content_integrity_preserves_versions_and_meaning() -> None:
    review = _sample_review(
        text="Updated to v8.2.1 and version 8.2.0 — onboarding is smooth",
    )
    corpus = scrub_reviews([review])
    text = corpus.reviews[0].text
    assert "v8.2.1" in text
    assert "8.2.0" in text
    assert "onboarding is smooth" in text


def test_fixture_zero_pii_leaks(pii_fixture: tuple[list[Review], list[str], list[str]]) -> None:
    reviews, must_not_contain, must_preserve = pii_fixture
    corpus = scrub_reviews(reviews)

    for review in corpus.reviews:
        combined = f"{review.title} {review.text}"
        for secret in must_not_contain:
            assert secret not in combined, f"PII leak: {secret!r} in review {review.id}"
        for needle in find_pii_matches(combined):
            assert False, f"Residual PII ({needle[0]}): {needle[1]!r} in review {review.id}"

    combined_output = " ".join(f"{r.title} {r.text}" for r in corpus.reviews)
    for fragment in must_preserve:
        assert fragment in combined_output, f"Lost non-PII content: {fragment!r}"


def test_redaction_counts_logged(pii_fixture: tuple[list[Review], list[str], list[str]]) -> None:
    reviews, _, _ = pii_fixture
    corpus = scrub_reviews(reviews)
    assert corpus.report.reviews_processed == len(reviews)
    assert corpus.report.total_redactions > 0
    assert corpus.report.fields_scrubbed >= 5


def test_scrub_text_idempotent_on_clean_text() -> None:
    text = "Great app for mutual funds and SIP."
    once, counts = scrub_text(text)
    twice, _ = scrub_text(once)
    assert once == twice
    assert counts.total() == 0
