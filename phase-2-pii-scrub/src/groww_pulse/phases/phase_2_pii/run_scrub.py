"""CLI entrypoint for Phase 2 PII scrubbing."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from groww_pulse.config import load_pii_settings
from groww_pulse.logging_setup import setup_logging
from groww_pulse.phases.phase_2_pii.io import load_reviews_from_phase1, write_scrubbed_output
from groww_pulse.phases.phase_2_pii.scrub import scrub_reviews


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Phase 2 — scrub PII from normalized Review[] (Phase 1 output).",
    )
    parser.add_argument(
        "--input",
        type=Path,
        help="Phase 1 normalized_reviews.json path",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/output/scrubbed_reviews.json"),
        help="Scrubbed JSON output path",
    )
    args = parser.parse_args(argv)

    logger = setup_logging()
    settings = load_pii_settings()
    input_path = args.input or settings.phase1_output

    if not input_path.is_file():
        logger.error("Input not found: %s", input_path)
        raise SystemExit(1)

    reviews, upstream_report = load_reviews_from_phase1(input_path)
    logger.info("Loaded %s reviews from %s", len(reviews), input_path)

    corpus = scrub_reviews(reviews, redaction_token=settings.redaction_token)
    write_scrubbed_output(args.output, corpus, upstream_report=upstream_report)
    logger.info("Wrote %s scrubbed reviews to %s", len(corpus.reviews), args.output)

    raise SystemExit(0)


if __name__ == "__main__":
    main()
