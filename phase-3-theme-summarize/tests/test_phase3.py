"""Phase 3 clustering and summarization tests."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from groww_pulse.config import SummarizationSettings
from groww_pulse.models import Pulse, PulseMeta, PulseQuote, PulseTheme
from groww_pulse.phases.phase_3_summarization.cluster import cluster_reviews, reviews_by_id
from groww_pulse.phases.phase_3_summarization.io import ScrubbedInputRequiredError, load_scrubbed_reviews
from groww_pulse.phases.phase_3_summarization.pipeline import run_phase3
from groww_pulse.phases.phase_3_summarization.repair import trim_word_count
from groww_pulse.phases.phase_3_summarization.validate import (
    count_pulse_words,
    quote_is_verbatim,
    validate_pulse,
)

FIXTURES = Path(__file__).resolve().parent.parent / "data" / "fixtures"
SAMPLE = FIXTURES / "scrubbed_sample.json"


@pytest.fixture
def dry_settings(monkeypatch: pytest.MonkeyPatch) -> SummarizationSettings:
    monkeypatch.setenv("DRY_RUN", "true")
    monkeypatch.setenv("GROQ_API_KEY", "")
    return SummarizationSettings(
        dry_run=True,
        groq_api_key="",
        embedding_model="sentence-transformers/all-MiniLM-L6-v2",
        cluster_k=3,
        top_themes=3,
        groq_reps_per_theme=4,
    )


def test_rejects_non_scrubbed_input(tmp_path: Path) -> None:
    bad = tmp_path / "bad.json"
    bad.write_text('{"reviews": []}', encoding="utf-8")
    with pytest.raises(ScrubbedInputRequiredError):
        load_scrubbed_reviews(bad)


def test_cluster_theme_cap(dry_settings: SummarizationSettings) -> None:
    reviews, _ = load_scrubbed_reviews(SAMPLE)
    corpus = cluster_reviews(
        reviews,
        embedding_model=dry_settings.embedding_model,
        cluster_k=dry_settings.cluster_k,
        top_n=3,
        reps_per_theme=4,
        random_state=42,
    )
    assert len(corpus.themes) <= 5
    assert len(corpus.top_theme_ids) == 3


def test_cluster_deterministic(dry_settings: SummarizationSettings) -> None:
    reviews, _ = load_scrubbed_reviews(SAMPLE)
    kwargs = dict(
        embedding_model=dry_settings.embedding_model,
        cluster_k=3,
        top_n=3,
        reps_per_theme=4,
        random_state=42,
    )
    first = cluster_reviews(reviews, **kwargs)
    second = cluster_reviews(reviews, **kwargs)
    assert first.top_theme_ids == second.top_theme_ids


def test_dry_run_pipeline(dry_settings: SummarizationSettings) -> None:
    pulse, corpus, report = run_phase3(
        input_path=SAMPLE,
        settings=dry_settings,
        week_of=date(2026, 6, 4),
    )
    assert len(corpus.themes) <= 5
    assert len(pulse.top_themes) == 3
    assert len(pulse.quotes) == 3
    assert len(pulse.action_ideas) == 3
    assert pulse.word_count <= 250
    assert report["calls_made"] == 0
    assert report["dry_run"] is True or not dry_settings.groq_api_key.strip()


def test_quote_fidelity_check() -> None:
    reviews, _ = load_scrubbed_reviews(SAMPLE)
    lookup = reviews_by_id(reviews)
    review = reviews[0]
    good = PulseQuote(review_id=review.id, text=review.text, theme_name="Support")
    bad = PulseQuote(review_id=review.id, text="invented quote text here", theme_name="Support")
    assert quote_is_verbatim(good, lookup) is True
    assert quote_is_verbatim(bad, lookup) is False


def test_trim_word_count() -> None:
    pulse = Pulse.model_construct(
        week_of=date(2026, 6, 4),
        top_themes=[
            PulseTheme(name="A", one_line_summary="word " * 40),
            PulseTheme(name="B", one_line_summary="word " * 40),
            PulseTheme(name="C", one_line_summary="word " * 40),
        ],
        quotes=[
            PulseQuote(review_id="1", text="quote " * 20, theme_name="A"),
            PulseQuote(review_id="2", text="quote " * 20, theme_name="B"),
            PulseQuote(review_id="3", text="quote " * 20, theme_name="C"),
        ],
        action_ideas=["action " * 20, "action " * 20, "action " * 20],
        word_count=999,
        meta=PulseMeta(review_count=1),
    )
    trimmed = trim_word_count(pulse)
    assert trimmed.word_count <= 250


def test_validate_pulse_structure(dry_settings: SummarizationSettings) -> None:
    pulse, _, _ = run_phase3(input_path=SAMPLE, settings=dry_settings, week_of=date(2026, 6, 4))
    lookup = reviews_by_id(load_scrubbed_reviews(SAMPLE)[0])
    pulse = pulse.model_copy(update={"word_count": count_pulse_words(pulse)})
    result = validate_pulse(pulse, lookup)
    assert result.ok is True
