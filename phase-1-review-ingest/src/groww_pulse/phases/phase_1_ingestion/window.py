"""Rolling date-window filter."""

from __future__ import annotations

from datetime import date, timedelta


def window_start(as_of: date, window_weeks: int) -> date:
    return as_of - timedelta(weeks=window_weeks)


def is_in_window(review_date: date, as_of: date, window_weeks: int) -> bool:
    start = window_start(as_of, window_weeks)
    return start <= review_date <= as_of
