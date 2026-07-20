"""Phase 4 data models."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field, field_validator


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
    generated_at: datetime | str | None = None
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


class DeliveryResult(BaseModel):
    week_of: date
    doc_id: str | None = None
    doc_url: str | None = None
    draft_id: str | None = None
    dry_run: bool = False
    tools_called: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors and (
            self.dry_run or (bool(self.doc_url) and bool(self.draft_id))
        )
