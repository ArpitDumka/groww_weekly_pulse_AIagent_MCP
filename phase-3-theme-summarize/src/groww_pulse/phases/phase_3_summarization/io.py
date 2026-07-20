"""Load Phase 2 scrubbed reviews."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from groww_pulse.models import Review, ThemedCorpus, Pulse


class ScrubbedInputRequiredError(ValueError):
    """Raised when input is not a Phase 2 scrubbed artifact."""


def load_scrubbed_reviews(path: Path) -> tuple[list[Review], dict[str, Any]]:
    if not path.is_file():
        raise FileNotFoundError(path)

    payload = json.loads(path.read_text(encoding="utf-8"))
    if "redaction_report" not in payload:
        raise ScrubbedInputRequiredError(
            "Input must be Phase 2 scrubbed_reviews.json (missing redaction_report). "
            "Do not pass normalized Phase 1 output directly to Phase 3.",
        )

    reviews = [Review.model_validate(item) for item in payload["reviews"]]
    return reviews, payload


def write_phase3_output(
    path: Path,
    *,
    pulse: Pulse,
    themed_corpus: ThemedCorpus,
    groq_report: dict[str, Any],
    upstream: dict[str, Any] | None = None,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "upstream_report": upstream or {},
        "themed_corpus": themed_corpus.model_dump(mode="json"),
        "groq_report": groq_report,
        "pulse": pulse.model_dump(mode="json"),
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
