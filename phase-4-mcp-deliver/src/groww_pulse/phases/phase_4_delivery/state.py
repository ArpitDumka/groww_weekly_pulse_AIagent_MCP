"""Idempotent delivery state for retries."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any


def load_state(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def save_state(path: Path, state: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2), encoding="utf-8")


def week_key(week_of: date) -> str:
    return week_of.isoformat()


def get_week_record(state: dict[str, Any], week_of: date) -> dict[str, Any]:
    return dict(state.get(week_key(week_of), {}))


def mark_week_delivered(
    state: dict[str, Any],
    *,
    week_of: date,
    doc_id: str,
    doc_url: str,
    draft_id: str,
) -> dict[str, Any]:
    state[week_key(week_of)] = {
        "doc_id": doc_id,
        "doc_url": doc_url,
        "draft_id": draft_id,
        "delivered": True,
    }
    return state
