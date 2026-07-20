#!/usr/bin/env python3
"""Download real Groww reviews from public App Store and Play Store endpoints."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from groww_pulse.config import load_ingestion_settings
from groww_pulse.logging_setup import setup_logging
from groww_pulse.phases.phase_1_ingestion.fetch_reviews import fetch_and_save


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Fetch real Groww reviews from public store APIs (no login required).",
    )
    parser.add_argument(
        "--count",
        type=int,
        default=20_000,
        help="Target reviews per store (default: 20000)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/raw"),
        help="Directory for CSV exports",
    )
    parser.add_argument("--play-lang", default="en")
    parser.add_argument("--play-country", default="in")
    parser.add_argument(
        "--stores",
        choices=("both", "play", "app"),
        default="both",
        help="Which store(s) to fetch (default: both)",
    )
    parser.add_argument(
        "--app-store-export",
        type=Path,
        help="Optional App Store Connect CSV export path",
    )
    args = parser.parse_args(argv)

    logger = setup_logging()
    settings = load_ingestion_settings()
    export_csv = args.app_store_export or settings.app_store_export_csv
    play_report, app_report = fetch_and_save(
        output_dir=args.output_dir,
        count_per_store=args.count,
        play_lang=args.play_lang,
        play_country=args.play_country,
        app_store_export_csv=export_csv,
        stores=args.stores,
    )

    summary = {}
    if play_report:
        summary["play_store"] = play_report.__dict__
        summary["play_store"]["output_path"] = str(play_report.output_path)
    if app_report:
        summary["app_store"] = app_report.__dict__
        summary["app_store"]["output_path"] = str(app_report.output_path)

    print(json.dumps(summary, indent=2))
    logger.info("Fetch complete.")
    raise SystemExit(0)


if __name__ == "__main__":
    main()
