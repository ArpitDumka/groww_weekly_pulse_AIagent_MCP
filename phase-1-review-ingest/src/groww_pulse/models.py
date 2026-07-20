"""Normalized review data model (architecture §3.1 / §4)."""

from __future__ import annotations

from datetime import date
from enum import Enum

from pydantic import BaseModel, Field, field_validator


class ReviewSource(str, Enum):
    APP_STORE = "app_store"
    PLAY_STORE = "play_store"


class Review(BaseModel):
    """Normalized review record — no reviewer identity fields."""

    id: str
    source: ReviewSource
    rating: int = Field(ge=1, le=5)
    title: str = ""
    text: str
    date: date
    app_version: str | None = None
    locale: str | None = None

    @field_validator("title", "text", mode="before")
    @classmethod
    def strip_strings(cls, value: object) -> object:
        if value is None:
            return "" if cls.model_fields["title"].default == "" else value
        if isinstance(value, str):
            return value.strip()
        return value

    @field_validator("text")
    @classmethod
    def text_not_empty(cls, value: str) -> str:
        if not value:
            raise ValueError("review text must not be empty")
        return value
