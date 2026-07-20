"""Ingestion-specific configuration."""

from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class IngestionSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    target_per_store: int = Field(default=20_000, ge=1, alias="TARGET_PER_STORE")
    min_word_count: int = Field(default=6, ge=1, alias="MIN_WORD_COUNT")
    english_only: bool = Field(default=True, alias="ENGLISH_ONLY")
    reject_emoji: bool = Field(default=True, alias="REJECT_EMOJI")
    app_store_export_csv: Path | None = Field(default=None, alias="APP_STORE_EXPORT_CSV")


def load_ingestion_settings() -> IngestionSettings:
    return IngestionSettings()
