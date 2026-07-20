"""Phase 3 configuration."""

from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class SummarizationSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    phase2_output: Path = Field(
        default=Path("../phase-2-pii-scrub/data/output/scrubbed_reviews.json"),
        alias="PHASE2_OUTPUT",
    )
    groq_api_key: str = Field(default="", alias="GROQ_API_KEY")
    groq_model: str = Field(default="llama-3.3-70b-versatile", alias="GROQ_MODEL")
    groq_max_calls_per_run: int = Field(default=2, ge=1, le=2, alias="GROQ_MAX_CALLS_PER_RUN")
    groq_max_tokens_per_run: int = Field(default=6000, ge=500, alias="GROQ_MAX_TOKENS_PER_RUN")
    groq_reps_per_theme: int = Field(default=6, ge=1, le=12, alias="GROQ_REPS_PER_THEME")
    groq_max_review_chars: int = Field(default=200, ge=50, alias="GROQ_MAX_REVIEW_CHARS")
    embedding_model: str = Field(
        default="sentence-transformers/all-MiniLM-L6-v2",
        alias="EMBEDDING_MODEL",
    )
    cluster_k: int = Field(default=5, ge=2, le=5, alias="CLUSTER_K")
    top_themes: int = Field(default=3, ge=1, le=3, alias="TOP_THEMES")
    word_budget: int = Field(default=250, ge=50, alias="WORD_BUDGET")
    dry_run: bool = Field(default=False, alias="DRY_RUN")
    cluster_random_state: int = Field(default=42, alias="CLUSTER_RANDOM_STATE")


def load_settings() -> SummarizationSettings:
    return SummarizationSettings()
