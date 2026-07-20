"""Deterministic Pulse repairs without extra Groq calls."""

from __future__ import annotations

import re
from datetime import date

from groww_pulse.models import (
    Pulse,
    PulseMeta,
    PulseQuote,
    PulseTheme,
    Review,
    ThemeCluster,
    ThemedCorpus,
)
from groww_pulse.phases.phase_3_summarization.cluster import source_split
from groww_pulse.phases.phase_3_summarization.validate import count_pulse_words, quote_is_verbatim


def _pick_quote_for_theme(
    theme: ThemeCluster,
    review_lookup: dict[str, Review],
    *,
    theme_name: str,
) -> PulseQuote | None:
    for review_id in theme.representatives:
        review = review_lookup.get(review_id)
        if review is None:
            continue
        text = review.text.strip()
        if not text:
            continue
        return PulseQuote(review_id=review.id, text=text, theme_name=theme_name)
    return None


def swap_invalid_quotes(pulse: Pulse, review_lookup: dict[str, Review]) -> Pulse:
    fixed_quotes: list[PulseQuote] = []
    for quote in pulse.quotes:
        if quote_is_verbatim(quote, review_lookup):
            fixed_quotes.append(quote)
            continue
        theme_name = quote.theme_name or "Theme"
        replacement = None
        for review_id, review in review_lookup.items():
            if review_id == quote.review_id:
                replacement = PulseQuote(
                    review_id=review.id,
                    text=review.text,
                    theme_name=theme_name,
                )
                break
        if replacement and quote_is_verbatim(replacement, review_lookup):
            fixed_quotes.append(replacement)
        else:
            fixed_quotes.append(
                PulseQuote(
                    review_id=quote.review_id,
                    text=review_lookup[quote.review_id].text
                    if quote.review_id in review_lookup
                    else quote.text,
                    theme_name=theme_name,
                )
            )
    return pulse.model_copy(update={"quotes": fixed_quotes})


_WORD_RE = re.compile(r"\b[\w'-]+\b")


def _truncate_to_word_prefix(text: str, max_words: int) -> str:
    """Return a verbatim prefix of ``text`` capped at ``max_words`` words.

    The prefix is sliced from the original string (preserving its exact
    characters) so it remains a genuine substring of the source review, then
    marked with an ellipsis. This shortens without inventing wording.
    """
    matches = list(_WORD_RE.finditer(text))
    if len(matches) <= max_words:
        return text
    end = matches[max_words - 1].end()
    return text[:end].rstrip(" ,.;:") + "\u2026"


def trim_word_count(pulse: Pulse, budget: int = 250) -> Pulse:
    # Recompute the real count rather than trusting the incoming word_count field
    # (the LLM often self-reports a value below the true count, which would make
    # this early-return skip trimming and leave an over-budget pulse).
    actual = count_pulse_words(pulse)
    pulse = pulse.model_copy(update={"word_count": actual})
    if actual <= budget:
        return pulse

    trimmed_themes: list[PulseTheme] = []
    for theme in pulse.top_themes:
        summary_words = theme.one_line_summary.split()
        if len(summary_words) > 12:
            summary_words = summary_words[:12]
        trimmed_themes.append(
            PulseTheme(name=theme.name, one_line_summary=" ".join(summary_words)),
        )

    trimmed_actions = [idea[:120].rstrip() for idea in pulse.action_ideas]
    updated = pulse.model_copy(
        update={"top_themes": trimmed_themes, "action_ideas": trimmed_actions},
    )
    updated = updated.model_copy(update={"word_count": count_pulse_words(updated)})
    if updated.word_count > budget:
        shorter_actions = [idea.split(".")[0][:80] for idea in trimmed_actions]
        updated = updated.model_copy(update={"action_ideas": shorter_actions})
        updated = updated.model_copy(update={"word_count": count_pulse_words(updated)})

    # Verbatim quotes can still dominate the budget. As a last resort, truncate
    # each quote to a shorter verbatim prefix until the note fits.
    if updated.word_count > budget:
        non_quote_parts: list[str] = []
        for theme in updated.top_themes:
            non_quote_parts.extend([theme.name, theme.one_line_summary])
        non_quote_parts.extend(updated.action_ideas)
        non_quote_words = len(
            _WORD_RE.findall(" ".join(part for part in non_quote_parts if part))
        )
        original_quotes = updated.quotes
        per_quote = max((budget - non_quote_words) // max(len(original_quotes), 1), 6)
        while per_quote >= 6:
            truncated_quotes = [
                quote.model_copy(
                    update={"text": _truncate_to_word_prefix(quote.text, per_quote)}
                )
                for quote in original_quotes
            ]
            candidate = updated.model_copy(update={"quotes": truncated_quotes})
            candidate = candidate.model_copy(
                update={"word_count": count_pulse_words(candidate)}
            )
            if candidate.word_count <= budget:
                return candidate
            per_quote -= 4
        updated = candidate
    return updated


def build_fallback_pulse(
    *,
    reviews: list[Review],
    themed_corpus: ThemedCorpus,
    review_lookup: dict[str, Review],
    week_of: date,
    groq_calls: int,
    tokens_estimated: int,
    dry_run: bool,
) -> Pulse:
    top = themed_corpus.top_themes[:3]
    while len(top) < 3:
        top.append(
            ThemeCluster(
                cluster_id=-len(top),
                size=0,
                avg_rating=0.0,
                severity=0.0,
                rank_score=0.0,
                rank=len(top) + 1,
                representatives=[],
            )
        )

    themes: list[PulseTheme] = []
    quotes: list[PulseQuote] = []
    for index, theme in enumerate(top[:3], start=1):
        name = f"Theme {index} (cluster {theme.cluster_id})"
        summary = (
            f"{theme.size} reviews, avg {theme.avg_rating:.1f} stars, "
            f"severity {theme.severity:.0%}."
        )
        themes.append(PulseTheme(name=name, one_line_summary=summary))
        quote = _pick_quote_for_theme(theme, review_lookup, theme_name=name)
        if quote:
            quotes.append(quote)

    while len(quotes) < 3:
        fallback_review = reviews[min(len(quotes), len(reviews) - 1)]
        quotes.append(
            PulseQuote(
                review_id=fallback_review.id,
                text=fallback_review.text,
                theme_name=themes[len(quotes)].name if len(quotes) < len(themes) else "Theme",
            )
        )

    actions = [
        f"Investigate recurring issues in {themes[0].name}.",
        f"Improve support turnaround for {themes[1].name}.",
        f"Prioritize fixes highlighted in {themes[2].name}.",
    ]

    pulse = Pulse(
        week_of=week_of,
        top_themes=themes,
        quotes=quotes[:3],
        action_ideas=actions,
        word_count=0,
        meta=PulseMeta(
            review_count=len(reviews),
            source_split=source_split(reviews),
            groq_calls=groq_calls,
            groq_tokens_estimated=tokens_estimated,
            dry_run=dry_run,
        ),
    )
    pulse = pulse.model_copy(update={"word_count": count_pulse_words(pulse)})
    return trim_word_count(pulse)
