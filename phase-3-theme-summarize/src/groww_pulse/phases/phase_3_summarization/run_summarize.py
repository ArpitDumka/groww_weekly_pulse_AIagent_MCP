"""CLI entrypoint for Phase 3."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

from groww_pulse.config import load_settings
from groww_pulse.logging_setup import setup_logging
from groww_pulse.phases.phase_3_summarization.io import load_scrubbed_reviews, write_phase3_output
from groww_pulse.phases.phase_3_summarization.pipeline import run_phase3


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Phase 3 — cluster scrubbed reviews and summarize with Groq.",
    )
    parser.add_argument("--input", type=Path, help="Phase 2 scrubbed_reviews.json path")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/output/pulse.json"),
    )
    parser.add_argument("--week-of", type=str, help="ISO date anchor (YYYY-MM-DD)")
    parser.add_argument("--dry-run", action="store_true", help="Skip Groq calls")
    args = parser.parse_args(argv)

    logger = setup_logging()
    settings = load_settings()
    if args.dry_run:
        settings = settings.model_copy(update={"dry_run": True})

    input_path = args.input or settings.phase2_output
    week_of = date.fromisoformat(args.week_of) if args.week_of else None

    _, upstream = load_scrubbed_reviews(input_path)

    pulse, themed, groq_report = run_phase3(
        input_path=input_path,
        settings=settings,
        week_of=week_of,
    )

    write_phase3_output(
        args.output,
        pulse=pulse,
        themed_corpus=themed,
        groq_report=groq_report,
        upstream=upstream,
    )
    logger.info("Wrote pulse to %s", args.output)

    if args.output.suffix == ".json" and "--quiet" not in (argv or sys.argv):
        print(json.dumps(pulse.model_dump(mode="json"), indent=2))

    raise SystemExit(0)


if __name__ == "__main__":
    main()
