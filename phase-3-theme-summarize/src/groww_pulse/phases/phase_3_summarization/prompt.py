"""Groq prompt construction."""

from __future__ import annotations

from groww_pulse.models import Review, ThemeCluster
from groww_pulse.phases.phase_3_summarization.tokens import build_rep_lines


SYSTEM_PROMPT = """You produce a weekly Groww app review pulse as strict JSON.

Rules:
- Exactly 3 top_themes objects with name and one_line_summary.
- Exactly 3 quotes; each quote.text MUST be copied verbatim from one provided review id.
- Each quote must include review_id matching a provided id.
- Exactly 3 action_ideas strings, concrete and grounded in the themes.
- Keep the combined note concise (target under 250 words total across summaries, quotes, and actions).
- Do not invent review text. Do not include PII.

Return JSON only with keys: top_themes, quotes, action_ideas.
Each quote object: {"review_id": "...", "text": "...", "theme_name": "..."}"""


def build_user_prompt(
    themes: list[ThemeCluster],
    review_lookup: dict[str, Review],
    *,
    max_reps: int,
    max_chars: int,
) -> str:
    sections: list[str] = ["Summarize these three review clusters into a pulse note."]
    for theme in themes:
        sections.append(
            f"\n## Cluster {theme.cluster_id}\n"
            f"size={theme.size}, avg_rating={theme.avg_rating}, severity={theme.severity}, "
            f"rank={theme.rank}",
        )
        sections.extend(
            build_rep_lines(theme, review_lookup, max_reps=max_reps, max_chars=max_chars),
        )
    sections.append(
        "\nPick one quote per theme from the ids above. Copy quote text exactly.",
    )
    return "\n".join(sections)


def shrink_reps(max_reps: int, estimated_tokens: int, token_budget: int) -> int:
    reps = max_reps
    while reps > 1 and estimated_tokens > token_budget:
        reps -= 1
    return reps
