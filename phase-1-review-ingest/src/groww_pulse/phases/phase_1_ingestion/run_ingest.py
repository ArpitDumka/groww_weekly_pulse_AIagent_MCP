"""CLI entrypoint for Phase 1 ingestion."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from groww_pulse.config import load_ingestion_settings
from groww_pulse.logging_setup import setup_logging
from groww_pulse.phases.phase_1_ingestion.filters import NormalizationFilterSettings
from groww_pulse.phases.phase_1_ingestion.ingest import ingest_reviews


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Phase 1 — ingest and normalize App Store + Play Store review exports.",
    )
    parser.add_argument("--app-store", type=Path, help="Path to App Store CSV export")
    parser.add_argument("--play-store", type=Path, help="Path to Play Store CSV export")
    parser.add_argument(
        "--output",
        type=Path,
        help="Optional JSON output path for normalized reviews",
    )
    parser.add_argument(
        "--limit-per-store",
        type=int,
        help="Max reviews to keep per store (default from .env TARGET_PER_STORE)",
    )
    args = parser.parse_args(argv)

    logger = setup_logging()
    settings = load_ingestion_settings()
    limit = args.limit_per_store or settings.target_per_store

    if args.app_store is None and args.play_store is None:
        logger.error("Provide --app-store and/or --play-store")
        raise SystemExit(1)

    reviews, report = ingest_reviews(
        app_store_path=args.app_store,
        play_store_path=args.play_store,
        limit_per_source=limit,
        filters=NormalizationFilterSettings(
            min_word_count=settings.min_word_count,
            english_only=settings.english_only,
            reject_emoji=settings.reject_emoji,
        ),
    )

    payload = {
        "report": report.__dict__,
        "reviews": [review.model_dump(mode="json") for review in reviews],
    }

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        logger.info("Wrote %s reviews to %s", len(reviews), args.output)
    else:
        print(json.dumps(payload, indent=2))

    raise SystemExit(0)


if __name__ == "__main__":
    main()
