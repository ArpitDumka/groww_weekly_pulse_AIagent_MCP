#!/usr/bin/env python3
"""Phase 2 end-to-end: scrub PII from Phase 1 normalized reviews."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Phase 2 PII scrubbing.")
    parser.add_argument(
        "--input",
        type=Path,
        help="Phase 1 normalized_reviews.json (default from .env)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/output/scrubbed_reviews.json"),
    )
    args = parser.parse_args()

    root = Path(__file__).resolve().parent.parent
    py = root / ".venv" / "Scripts" / "python.exe"
    if not py.is_file():
        py = Path(sys.executable)

    cmd = [
        str(py),
        "-m",
        "groww_pulse.phases.phase_2_pii.run_scrub",
        "--output",
        str(args.output),
    ]
    if args.input:
        cmd.extend(["--input", str(args.input)])

    subprocess.run(cmd, cwd=root, check=True)


if __name__ == "__main__":
    main()
