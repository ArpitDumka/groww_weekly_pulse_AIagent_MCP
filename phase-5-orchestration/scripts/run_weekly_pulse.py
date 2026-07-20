#!/usr/bin/env python3
"""Phase 5 orchestrator: run the full weekly pulse pipeline end-to-end.

Chains the existing Phase 1-4 logic in order, each in its own per-phase
virtualenv (the phases share the ``groww_pulse`` package name and therefore
cannot coexist in a single environment):

    ingest (fetch fresh reviews) -> scrub -> cluster+summarize -> deliver (MCP)

Designed to be invoked either locally or from the weekly GitHub Actions job
(see ``.github/workflows/weekly-pulse.yml``). Delivery reaches the Google MCP
server over ``MCP_SERVER_BASE_URL`` (default ``http://127.0.0.1:8000``); in CI
that server runs inside the same runner (Option A).
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

PHASE1_DIR = REPO_ROOT / "phase-1-review-ingest"
PHASE2_DIR = REPO_ROOT / "phase-2-pii-scrub"
PHASE3_DIR = REPO_ROOT / "phase-3-theme-summarize"
PHASE4_DIR = REPO_ROOT / "phase-4-mcp-deliver"

PHASE1_WEEKLY = PHASE1_DIR / "data" / "output" / "normalized_reviews.json"
# Persistent, deduped corpus that grows each week (accumulation).
CORPUS_PATH = PHASE1_DIR / "data" / "output" / "corpus.json"
PHASE3_PULSE = PHASE3_DIR / "data" / "output" / "pulse.json"
PHASE4_RESULT = PHASE4_DIR / "data" / "output" / "delivery_result.json"


def venv_python(phase_dir: Path) -> Path:
    """Return the phase's venv interpreter, or the current one as a fallback."""
    if os.name == "nt":
        candidate = phase_dir / ".venv" / "Scripts" / "python.exe"
    else:
        candidate = phase_dir / ".venv" / "bin" / "python"
    return candidate if candidate.is_file() else Path(sys.executable)


def most_recent_monday(today: dt.date | None = None) -> str:
    today = today or dt.date.today()
    monday = today - dt.timedelta(days=today.weekday())
    return monday.isoformat()


def run(cmd: list[str], cwd: Path, env: dict[str, str] | None = None) -> None:
    printable = " ".join(str(part) for part in cmd)
    print(f"\n$ (cd {cwd}) {printable}", flush=True)
    subprocess.run(cmd, cwd=cwd, check=True, env=env)


# --------------------------------------------------------------------------- #
# Setup (used by CI and for first-time local runs)
# --------------------------------------------------------------------------- #

def setup_phase(phase_dir: Path) -> None:
    """Create the phase venv (if missing) and install its dependencies."""
    if os.name == "nt":
        py = phase_dir / ".venv" / "Scripts" / "python.exe"
    else:
        py = phase_dir / ".venv" / "bin" / "python"

    if not py.is_file():
        print(f"\n== creating venv for {phase_dir.name} ==", flush=True)
        subprocess.run([sys.executable, "-m", "venv", str(phase_dir / ".venv")], check=True)

    subprocess.run([str(py), "-m", "pip", "install", "--upgrade", "pip"], cwd=phase_dir, check=True)

    if (phase_dir / "pyproject.toml").is_file():
        subprocess.run([str(py), "-m", "pip", "install", "-e", "."], cwd=phase_dir, check=True)
    requirements = phase_dir / "requirements.txt"
    if requirements.is_file():
        subprocess.run(
            [str(py), "-m", "pip", "install", "-r", str(requirements)],
            cwd=phase_dir,
            check=True,
        )


def do_setup() -> None:
    for phase_dir in (PHASE1_DIR, PHASE2_DIR, PHASE3_DIR, PHASE4_DIR):
        setup_phase(phase_dir)


# --------------------------------------------------------------------------- #
# Pipeline stages
# --------------------------------------------------------------------------- #

def run_phase1(count: int) -> None:
    py = venv_python(PHASE1_DIR)
    raw_dir = PHASE1_DIR / "data" / "raw"
    run(
        [str(py), "scripts/fetch_reviews.py", "--count", str(count), "--output-dir", str(raw_dir)],
        cwd=PHASE1_DIR,
    )
    run(
        [
            str(py),
            "-m",
            "groww_pulse.phases.phase_1_ingestion.run_ingest",
            "--app-store",
            str(raw_dir / "app_store_reviews.csv"),
            "--play-store",
            str(raw_dir / "play_store_reviews.csv"),
            "--limit-per-store",
            str(count),
            "--output",
            "data/output/normalized_reviews.json",
        ],
        cwd=PHASE1_DIR,
    )


def _read_payload(path: Path) -> dict:
    if path.is_file():
        return json.loads(path.read_text(encoding="utf-8"))
    return {"report": {}, "reviews": []}


def merge_into_corpus() -> tuple[int, int]:
    """Merge this week's fetched reviews into the persistent corpus (dedup by id).

    Returns (corpus_total, added_this_week). The corpus keeps every unique review
    ever ingested; review ids are content hashes, so re-fetched reviews dedup
    cleanly and only genuinely new ones grow the total.
    """
    weekly = _read_payload(PHASE1_WEEKLY)
    existing = _read_payload(CORPUS_PATH)
    existing_reviews = existing.get("reviews", [])

    by_id: dict[str, dict] = {r["id"]: r for r in existing_reviews if r.get("id")}
    added = 0
    for review in weekly.get("reviews", []):
        rid = review.get("id")
        if rid and rid not in by_id:
            by_id[rid] = review
            added += 1

    merged = list(by_id.values())
    by_source: dict[str, int] = {}
    for review in merged:
        source = review.get("source", "unknown")
        by_source[source] = by_source.get(source, 0) + 1

    report = dict(weekly.get("report", {}))
    prev_report = existing.get("report", {})
    report.update(
        {
            "final_count": len(merged),
            "by_source": by_source,
            "sources": sorted(by_source),
            "added_this_week": added,
            "previous_total": len(existing_reviews),
            "corpus_total": len(merged),
            "weeks_accumulated": int(prev_report.get("weeks_accumulated", 0)) + 1,
            "last_updated": dt.datetime.now().astimezone().isoformat(),
        }
    )

    CORPUS_PATH.parent.mkdir(parents=True, exist_ok=True)
    CORPUS_PATH.write_text(
        json.dumps({"report": report, "reviews": merged}, indent=2),
        encoding="utf-8",
    )
    print(
        f"Corpus merge: +{added} new this week, "
        f"{len(existing_reviews)} -> {len(merged)} total "
        f"(week {report['weeks_accumulated']})",
        flush=True,
    )
    return len(merged), added


def run_phase2(input_path: Path) -> None:
    py = venv_python(PHASE2_DIR)
    env = dict(os.environ)
    env["PHASE1_OUTPUT"] = str(input_path)
    run(
        [
            str(py),
            "-m",
            "groww_pulse.phases.phase_2_pii.run_scrub",
            "--input",
            str(input_path),
            "--output",
            "data/output/scrubbed_reviews.json",
        ],
        cwd=PHASE2_DIR,
        env=env,
    )


def run_phase3(week_of: str, dry_run: bool) -> None:
    py = venv_python(PHASE3_DIR)
    cmd = [
        str(py),
        "-m",
        "groww_pulse.phases.phase_3_summarization.run_summarize",
        "--output",
        "data/output/pulse.json",
        "--week-of",
        week_of,
    ]
    if dry_run:
        cmd.append("--dry-run")
    run(cmd, cwd=PHASE3_DIR)


def run_phase4(dry_run: bool) -> None:
    py = venv_python(PHASE4_DIR)
    env = dict(os.environ)
    # Phase 4 defaults to pulse_dashboard.json (built by the dashboard). The raw
    # pulse.json is always produced by Phase 3 and loads fine, so point at it.
    env["PHASE3_PULSE_INPUT"] = str(PHASE3_PULSE)
    cmd = [str(py), "-m", "groww_pulse.phases.phase_4_delivery.run_deliver"]
    if dry_run:
        cmd.append("--dry-run")
    run(cmd, cwd=PHASE4_DIR, env=env)


# --------------------------------------------------------------------------- #
# Run summary
# --------------------------------------------------------------------------- #

def print_summary(dry_run: bool) -> None:
    print("\n" + "=" * 60)
    print("WEEKLY PULSE — RUN SUMMARY")
    print("=" * 60)

    if PHASE3_PULSE.is_file():
        raw = json.loads(PHASE3_PULSE.read_text(encoding="utf-8"))
        upstream = raw.get("upstream_report", {})
        ingest = upstream.get("upstream_report", {})
        redaction = upstream.get("redaction_report", {})
        pulse = raw.get("pulse", {})
        if ingest:
            print(f"Corpus total reviews   : {ingest.get('final_count', '?')} "
                  f"(by source: {ingest.get('by_source', {})})")
            if "added_this_week" in ingest:
                print(f"Added this week        : {ingest.get('added_this_week')} "
                      f"(week {ingest.get('weeks_accumulated', '?')})")
        if redaction:
            print(f"PII redactions         : {redaction.get('total_redactions', '?')} "
                  f"across {redaction.get('fields_scrubbed', '?')} fields")
        themes = [t.get("name") for t in pulse.get("top_themes", [])]
        if themes:
            print(f"Top themes             : {', '.join(themes)}")
        print(f"Pulse word count       : {pulse.get('word_count', '?')}")

    if dry_run:
        print("Delivery               : SKIPPED (dry-run)")
    elif PHASE4_RESULT.is_file():
        result = json.loads(PHASE4_RESULT.read_text(encoding="utf-8")).get("delivery", {})
        print(f"Google Doc             : {result.get('doc_url')}")
        print(f"Gmail draft id         : {result.get('draft_id')}")
        if result.get("errors"):
            print(f"Delivery errors        : {result['errors']}")
    print("=" * 60, flush=True)


# --------------------------------------------------------------------------- #

def main() -> None:
    parser = argparse.ArgumentParser(description="Run the full weekly pulse pipeline.")
    parser.add_argument(
        "--count",
        type=int,
        default=int(os.environ.get("PULSE_FETCH_COUNT", "20000")),
        help="Target reviews per store to fetch (default 20000 or $PULSE_FETCH_COUNT).",
    )
    parser.add_argument("--week-of", type=str, help="ISO date anchor (default: most recent Monday).")
    parser.add_argument("--dry-run", action="store_true", help="Build the pulse but skip MCP delivery.")
    parser.add_argument("--setup", action="store_true", help="Create per-phase venvs and install deps, then exit.")
    parser.add_argument(
        "--skip-fetch",
        action="store_true",
        help="Skip Phase 1 fetch/ingest and reuse existing normalized reviews.",
    )
    parser.add_argument(
        "--no-accumulate",
        action="store_true",
        help="Do not merge into the persistent corpus; use only this week's batch.",
    )
    parser.add_argument(
        "--reset-corpus",
        action="store_true",
        help="Delete the persistent corpus before merging (start accumulation fresh).",
    )
    args = parser.parse_args()

    if args.setup:
        do_setup()
        print("\nSetup complete for all phases.")
        return

    week_of = args.week_of or most_recent_monday()
    accumulate = not args.no_accumulate
    print(
        f"Weekly pulse run — week_of={week_of} dry_run={args.dry_run} "
        f"count={args.count} accumulate={accumulate}"
    )

    if not args.skip_fetch:
        run_phase1(args.count)

    if args.reset_corpus and CORPUS_PATH.is_file():
        CORPUS_PATH.unlink()
        print("Reset corpus: existing corpus.json deleted.")

    if accumulate:
        merge_into_corpus()
        phase2_input = CORPUS_PATH
    else:
        phase2_input = PHASE1_WEEKLY

    run_phase2(phase2_input)
    run_phase3(week_of, args.dry_run)
    run_phase4(args.dry_run)

    print_summary(args.dry_run)


if __name__ == "__main__":
    main()
