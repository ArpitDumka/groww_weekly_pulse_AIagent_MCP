"""Phase 3 end-to-end pipeline."""

from __future__ import annotations

import logging
from datetime import date
from pathlib import Path
from typing import Any

from groww_pulse.config import SummarizationSettings, load_settings
from groww_pulse.models import Pulse, ThemedCorpus
from groww_pulse.phases.phase_3_summarization.cluster import cluster_reviews, reviews_by_id
from groww_pulse.phases.phase_3_summarization.groq_summarize import summarize_with_groq
from groww_pulse.phases.phase_3_summarization.io import load_scrubbed_reviews
from groww_pulse.phases.phase_3_summarization.validate import validate_pulse

logger = logging.getLogger("groww_pulse.summarize")


def run_phase3(
    *,
    input_path: Path | None = None,
    settings: SummarizationSettings | None = None,
    week_of: date | None = None,
) -> tuple[Pulse, ThemedCorpus, dict[str, Any]]:
    cfg = settings or load_settings()
    path = input_path or cfg.phase2_output

    reviews, upstream = load_scrubbed_reviews(path)
    logger.info("Loaded %s scrubbed reviews from %s", len(reviews), path)

    themed = cluster_reviews(
        reviews,
        embedding_model=cfg.embedding_model,
        cluster_k=cfg.cluster_k,
        top_n=cfg.top_themes,
        reps_per_theme=cfg.groq_reps_per_theme,
        random_state=cfg.cluster_random_state,
    )

    review_lookup = reviews_by_id(reviews)
    top_clusters = themed.top_themes
    if len(top_clusters) < cfg.top_themes:
        logger.warning("Only %s clusters available for top themes", len(top_clusters))

    pulse, groq_budget = summarize_with_groq(
        reviews=reviews,
        top_themes=top_clusters,
        review_lookup=review_lookup,
        settings=cfg,
        week_of=week_of,
    )

    validation = validate_pulse(pulse, review_lookup)
    if not validation.ok:
        logger.warning("Pulse validation warnings after repair: %s", validation.errors)

    groq_report = {
        "calls_made": groq_budget.calls_made,
        "max_calls": groq_budget.max_calls,
        "tokens_estimated": groq_budget.tokens_estimated,
        "max_tokens": groq_budget.max_tokens,
        "errors": groq_budget.errors,
        "validation_ok": validation.ok,
        "validation_errors": validation.errors,
        "dry_run": cfg.dry_run or not cfg.groq_api_key.strip(),
        "model": cfg.groq_model,
    }

    logger.info(
        "Phase 3 complete: themes=%s groq_calls=%s word_count=%s validation_ok=%s",
        len(themed.themes),
        groq_budget.calls_made,
        pulse.word_count,
        validation.ok,
    )

    return pulse, themed, groq_report
