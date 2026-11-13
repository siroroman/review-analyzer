from typing import Protocol

from pydantic import BaseModel, ConfigDict

from app.domain import Review


class InjectionDetector(Protocol):
    """Port: decides whether a cleaned Review text holds instructions aimed at a model. May raise."""

    def is_injection(self, text: str) -> bool: ...


class PreparedReviews(BaseModel):
    """The result of sanitizing: Reviews safe for the analysis, Flagged reviews, and what was dropped."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    clean: list[Review]
    flagged: list[Review]
    duplicates: int
    empty: int
