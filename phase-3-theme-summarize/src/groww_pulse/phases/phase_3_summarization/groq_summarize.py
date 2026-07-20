"""Groq API integration with call/token budget."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from groq import Groq

from groww_pulse.config import SummarizationSettings
from groww_pulse.models import (
    Pulse,
    PulseMeta,
    PulseQuote,
    PulseTheme,
    Review,
    ThemeCluster,
)
from groww_pulse.phases.phase_3_summarization.cluster import source_split
from groww_pulse.phases.phase_3_summarization.prompt import SYSTEM_PROMPT, build_user_prompt, shrink_reps
from groww_pulse.phases.phase_3_summarization.repair import build_fallback_pulse, swap_invalid_quotes, trim_word_count
from groww_pulse.phases.phase_3_summarization.tokens import estimate_prompt_tokens
from groww_pulse.phases.phase_3_summarization.validate import count_pulse_words, validate_pulse

logger = logging.getLogger("groww_pulse.summarize")


@dataclass
class GroqBudget:
    max_calls: int
    max_tokens: int
    calls_made: int = 0
    tokens_estimated: int = 0
    errors: list[str] = field(default_factory=list)

    def can_call(self) -> bool:
        return self.calls_made < self.max_calls


def _parse_groq_json(content: str) -> dict[str, Any]:
    text = content.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1]
        if text.endswith("```"):
            text = text.rsplit("```", 1)[0]
    return json.loads(text)


def _response_to_pulse(
    payload: dict[str, Any],
    *,
    week_of: date,
    reviews: list[Review],
    groq_budget: GroqBudget,
    dry_run: bool,
) -> Pulse:
    themes = [
        PulseTheme(name=item["name"], one_line_summary=item["one_line_summary"])
        for item in payload["top_themes"]
    ][:3]
    quotes = [
        PulseQuote(
            review_id=item["review_id"],
            text=item["text"],
            theme_name=item.get("theme_name", ""),
        )
        for item in payload["quotes"]
    ][:3]
    actions = list(payload["action_ideas"])[:3]

    pulse = Pulse(
        week_of=week_of,
        top_themes=themes,
        quotes=quotes,
        action_ideas=actions,
        word_count=0,
        meta=PulseMeta(
            review_count=len(reviews),
            source_split=source_split(reviews),
            groq_calls=groq_budget.calls_made,
            groq_tokens_estimated=groq_budget.tokens_estimated,
            dry_run=dry_run,
        ),
    )
    return pulse.model_copy(update={"word_count": count_pulse_words(pulse)})


def summarize_with_groq(
    *,
    reviews: list[Review],
    top_themes: list[ThemeCluster],
    review_lookup: dict[str, Review],
    settings: SummarizationSettings,
    week_of: date | None = None,
) -> tuple[Pulse, GroqBudget]:
    week = week_of or date.today()
    budget = GroqBudget(
        max_calls=settings.groq_max_calls_per_run,
        max_tokens=settings.groq_max_tokens_per_run,
    )

    if settings.dry_run or not settings.groq_api_key.strip():
        logger.info("DRY_RUN or missing GROQ_API_KEY — using deterministic fallback pulse")
        pulse = build_fallback_pulse(
            reviews=reviews,
            themed_corpus=_mini_corpus(top_themes),
            review_lookup=review_lookup,
            week_of=week,
            groq_calls=0,
            tokens_estimated=0,
            dry_run=True,
        )
        return pulse, budget

    reps = settings.groq_reps_per_theme
    estimated = estimate_prompt_tokens(
        themes=top_themes,
        review_lookup=review_lookup,
        max_reps=reps,
        max_chars=settings.groq_max_review_chars,
        system_prompt=SYSTEM_PROMPT,
    )
    reps = shrink_reps(reps, estimated, settings.groq_max_tokens_per_run)
    estimated = estimate_prompt_tokens(
        themes=top_themes,
        review_lookup=review_lookup,
        max_reps=reps,
        max_chars=settings.groq_max_review_chars,
        system_prompt=SYSTEM_PROMPT,
    )
    budget.tokens_estimated = estimated

    user_prompt = build_user_prompt(
        top_themes,
        review_lookup,
        max_reps=reps,
        max_chars=settings.groq_max_review_chars,
    )

    client = Groq(api_key=settings.groq_api_key)
    pulse: Pulse | None = None

    if budget.can_call():
        pulse = _call_groq(client, settings, user_prompt, budget, week, reviews)

    if pulse is None and budget.can_call():
        repair_prompt = (
            user_prompt
            + "\n\nPrevious response was invalid. Return valid JSON with exactly 3 themes, 3 quotes, 3 actions."
        )
        pulse = _call_groq(client, settings, repair_prompt, budget, week, reviews)

    if pulse is None:
        logger.warning("Groq unavailable or invalid — using deterministic fallback pulse")
        pulse = build_fallback_pulse(
            reviews=reviews,
            themed_corpus=_mini_corpus(top_themes),
            review_lookup=review_lookup,
            week_of=week,
            groq_calls=budget.calls_made,
            tokens_estimated=budget.tokens_estimated,
            dry_run=False,
        )

    pulse = swap_invalid_quotes(pulse, review_lookup)
    validation = validate_pulse(pulse, review_lookup)
    if not validation.ok:
        logger.info("Applying deterministic repairs: %s", validation.errors)
    pulse = trim_word_count(pulse, settings.word_budget)
    pulse = pulse.model_copy(
        update={
            "word_count": count_pulse_words(pulse),
            "meta": pulse.meta.model_copy(
                update={
                    "groq_calls": budget.calls_made,
                    "groq_tokens_estimated": budget.tokens_estimated,
                }
            ),
        }
    )
    return pulse, budget


def _mini_corpus(top_themes: list[ThemeCluster]):
    from groww_pulse.models import ThemedCorpus

    return ThemedCorpus(
        themes=top_themes,
        total_reviews=0,
        cluster_k=len(top_themes),
        top_theme_ids=[theme.cluster_id for theme in top_themes],
    )


def _call_groq(
    client: Groq,
    settings: SummarizationSettings,
    user_prompt: str,
    budget: GroqBudget,
    week_of: date,
    reviews: list[Review],
) -> Pulse | None:
    try:
        response = client.chat.completions.create(
            model=settings.groq_model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0.2,
        )
        budget.calls_made += 1
        content = response.choices[0].message.content or ""
        budget.tokens_estimated += len(content) // 4
        payload = _parse_groq_json(content)
        return _response_to_pulse(
            payload,
            week_of=week_of,
            reviews=reviews,
            groq_budget=budget,
            dry_run=settings.dry_run,
        )
    except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        budget.errors.append(str(exc))
        logger.warning("Groq response parse failed: %s", exc)
        return None
    except Exception as exc:  # noqa: BLE001 - log and fallback
        budget.errors.append(str(exc))
        logger.warning("Groq call failed: %s", exc)
        return None
