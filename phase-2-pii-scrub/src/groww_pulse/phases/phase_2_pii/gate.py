"""Hard gate: block LLM/artifact paths until scrubbing completes (ADR-002)."""

from __future__ import annotations

from typing import TypeVar

from groww_pulse.models import Review
from groww_pulse.phases.phase_2_pii.scrub import ScrubbedCorpus

T = TypeVar("T")


class ScrubbingRequiredError(RuntimeError):
    """Raised when unscrubbed review text reaches a protected boundary."""


def require_scrubbed_before_llm(corpus: ScrubbedCorpus | list[Review] | tuple[Review, ...]) -> ScrubbedCorpus:
    """Allow only a ScrubbedCorpus from scrub_reviews() to proceed to summarization."""
    if not isinstance(corpus, ScrubbedCorpus):
        raise ScrubbingRequiredError(
            "Reviews must pass through scrub_reviews() before any LLM call. "
            "Raw Review[] is not allowed past the PII boundary.",
        )
    return corpus


def require_scrubbed_before_artifact_write(
    corpus: ScrubbedCorpus | list[Review] | tuple[Review, ...],
) -> ScrubbedCorpus:
    """Same gate for Google Doc / Gmail draft writes."""
    return require_scrubbed_before_llm(corpus)


def simulate_llm_call(corpus: ScrubbedCorpus) -> str:
    """Test helper representing a downstream LLM stage."""
    validated = require_scrubbed_before_llm(corpus)
    return f"ok:{len(validated.reviews)}"
