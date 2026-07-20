#!/usr/bin/env python3
"""Run Phase 4 MCP delivery."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def main() -> None:
    root = Path(__file__).resolve().parent.parent
    py = root / ".venv" / "Scripts" / "python.exe"
    if not py.is_file():
        py = Path(sys.executable)

    cmd = [str(py), "-m", "groww_pulse.phases.phase_4_delivery.run_deliver", *sys.argv[1:]]
    subprocess.run(cmd, cwd=root, check=True)


if __name__ == "__main__":
    main()
