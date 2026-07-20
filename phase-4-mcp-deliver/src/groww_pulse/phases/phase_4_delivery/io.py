"""Load Pulse JSON from Phase 3 output."""

from __future__ import annotations

import json
from pathlib import Path

from groww_pulse.models import Pulse


def load_pulse(path: Path) -> Pulse:
    raw = json.loads(path.read_text(encoding="utf-8"))
    payload = raw.get("pulse", raw)
    return Pulse.model_validate(payload)
