"""Rough token estimation for Groq budget checks."""

from __future__ import annotations

from groww_pulse.models import Review, ThemeCluster


def truncate_review_text(text: str, max_chars: int) -> str:
    text = text.strip()
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 3].rstrip() + "..."


def estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


def build_rep_lines(
    theme: ThemeCluster,
    review_lookup: dict[str, Review],
    *,
    max_reps: int,
    max_chars: int,
) -> list[str]:
    lines: list[str] = []
    for review_id in theme.representatives[:max_reps]:
        review = review_lookup.get(review_id)
        if review is None:
            continue
        body = review.text if not review.title else f"{review.title}. {review.text}"
        snippet = truncate_review_text(body, max_chars)
        lines.append(f'- id={review.id} rating={review.rating} text="{snippet}"')
    return lines


def estimate_prompt_tokens(
    *,
    themes: list[ThemeCluster],
    review_lookup: dict[str, Review],
    max_reps: int,
    max_chars: int,
    system_prompt: str,
) -> int:
    parts = [system_prompt]
    for theme in themes:
        parts.append(
            f"Cluster {theme.cluster_id}: size={theme.size} avg_rating={theme.avg_rating} "
            f"severity={theme.severity}",
        )
        parts.extend(
            build_rep_lines(theme, review_lookup, max_reps=max_reps, max_chars=max_chars),
        )
    return sum(estimate_tokens(part) for part in parts) + 400
