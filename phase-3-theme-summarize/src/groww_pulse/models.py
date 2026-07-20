"""Shared data models (architecture §4)."""

from __future__ import annotations

from datetime import date, datetime
from enum import Enum

from pydantic import BaseModel, Field, field_validator


class ReviewSource(str, Enum):
    APP_STORE = "app_store"
    PLAY_STORE = "play_store"


class Review(BaseModel):
    id: str
    source: ReviewSource
    rating: int = Field(ge=1, le=5)
    title: str = ""
    text: str
    date: date
    app_version: str | None = None
    locale: str | None = None


class ThemeCluster(BaseModel):
    cluster_id: int
    size: int
    avg_rating: float
    severity: float = Field(ge=0.0, le=1.0)
    rank_score: float
    rank: int = 0
    representatives: list[str] = Field(default_factory=list)


class ThemedCorpus(BaseModel):
    themes: list[ThemeCluster] = Field(default_factory=list)
    total_reviews: int = 0
    cluster_k: int = 5
    embedding_model: str = ""
    top_theme_ids: list[int] = Field(default_factory=list)

    @property
    def top_themes(self) -> list[ThemeCluster]:
        top_ids = set(self.top_theme_ids)
        return [theme for theme in self.themes if theme.cluster_id in top_ids]


class PulseTheme(BaseModel):
    name: str
    one_line_summary: str


class PulseQuote(BaseModel):
    review_id: str
    text: str
    theme_name: str = ""


class PulseMeta(BaseModel):
    review_count: int
    source_split: dict[str, int] = Field(default_factory=dict)
    generated_at: datetime = Field(default_factory=lambda: datetime.now().astimezone())
    groq_calls: int = 0
    groq_tokens_estimated: int = 0
    dry_run: bool = False


class Pulse(BaseModel):
    week_of: date
    top_themes: list[PulseTheme] = Field(min_length=3, max_length=3)
    quotes: list[PulseQuote] = Field(min_length=3, max_length=3)
    action_ideas: list[str] = Field(min_length=3, max_length=3)
    word_count: int = Field(ge=0)
    meta: PulseMeta

    @field_validator("word_count")
    @classmethod
    def within_budget(cls, value: int) -> int:
        if value > 250:
            raise ValueError("word_count exceeds 250-word budget")
        return value


class GroqCallReport(BaseModel):
    calls_made: int = 0
    tokens_estimated: int = 0
