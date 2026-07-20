"""Load/save Phase 1 and Phase 2 JSON artifacts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from groww_pulse.models import Review
from groww_pulse.phases.phase_2_pii.scrub import RedactionReport, ScrubbedCorpus


def load_reviews_from_phase1(path: Path) -> tuple[list[Review], dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    reviews = [Review.model_validate(item) for item in payload["reviews"]]
    upstream_report = payload.get("report", {})
    return reviews, upstream_report


def write_scrubbed_output(
    path: Path,
    corpus: ScrubbedCorpus,
    *,
    upstream_report: dict[str, Any] | None = None,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "upstream_report": upstream_report or {},
        "redaction_report": {
            "reviews_processed": corpus.report.reviews_processed,
            "fields_scrubbed": corpus.report.fields_scrubbed,
            "total_redactions": corpus.report.total_redactions,
            "by_category": corpus.report.by_category,
            "ambiguous_redactions": corpus.report.ambiguous_redactions,
        },
        "reviews": [review.model_dump(mode="json") for review in corpus.reviews],
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
