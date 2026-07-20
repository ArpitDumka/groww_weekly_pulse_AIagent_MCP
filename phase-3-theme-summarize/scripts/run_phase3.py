#!/usr/bin/env python3
"""Run Phase 3 clustering + Groq summarization."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Phase 3 summarize pipeline.")
    parser.add_argument("--input", type=Path)
    parser.add_argument("--output", type=Path, default=Path("data/output/pulse.json"))
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--week-of", type=str)
    args = parser.parse_args()

    root = Path(__file__).resolve().parent.parent
    py = root / ".venv" / "Scripts" / "python.exe"
    if not py.is_file():
        py = Path(sys.executable)

    cmd = [
        str(py),
        "-m",
        "groww_pulse.phases.phase_3_summarization.run_summarize",
        "--output",
        str(args.output),
    ]
    if args.input:
        cmd.extend(["--input", str(args.input)])
    if args.dry_run:
        cmd.append("--dry-run")
    if args.week_of:
        cmd.extend(["--week-of", args.week_of])

    subprocess.run(cmd, cwd=root, check=True)


if __name__ == "__main__":
    main()
