#!/usr/bin/env python3
"""Phase 1 end-to-end: fetch real reviews then ingest (no date window)."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch + ingest Phase 1 reviews.")
    parser.add_argument("--count", type=int, default=20_000)
    parser.add_argument("--data-dir", type=Path, default=Path("data/raw"))
    parser.add_argument("--output", type=Path, default=Path("data/output/normalized_reviews.json"))
    args = parser.parse_args()

    root = Path(__file__).resolve().parent.parent
    py = root / ".venv" / "Scripts" / "python.exe"
    if not py.is_file():
        py = Path(sys.executable)

    fetch_cmd = [
        str(py),
        str(root / "scripts" / "fetch_reviews.py"),
        "--count",
        str(args.count),
        "--output-dir",
        str(args.data_dir),
    ]
    ingest_cmd = [
        str(py),
        "-m",
        "groww_pulse.phases.phase_1_ingestion.run_ingest",
        "--app-store",
        str(args.data_dir / "app_store_reviews.csv"),
        "--play-store",
        str(args.data_dir / "play_store_reviews.csv"),
        "--limit-per-store",
        str(args.count),
        "--output",
        str(args.output),
    ]

    subprocess.run(fetch_cmd, cwd=root, check=True)
    subprocess.run(ingest_cmd, cwd=root, check=True)


if __name__ == "__main__":
    main()
