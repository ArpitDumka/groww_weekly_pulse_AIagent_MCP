"""Phase 2 PII scrubbing configuration."""

from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class PiiSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    redaction_token: str = Field(default="[REDACTED]", alias="REDACTION_TOKEN")
    phase1_output: Path = Field(
        default=Path("../phase-1-review-ingest/data/output/normalized_reviews.json"),
        alias="PHASE1_OUTPUT",
    )


def load_pii_settings() -> PiiSettings:
    return PiiSettings()
