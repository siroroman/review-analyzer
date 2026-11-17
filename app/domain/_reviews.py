from datetime import date
from enum import StrEnum
from typing import Annotated

from pydantic import Field

from app.domain._base import DomainModel
from app.domain._places import Source

Rating = Annotated[int, Field(ge=1, le=5)]


class DatePrecision(StrEnum):
    """How exactly a Source states when a Review was written (some give only a month or a year)."""

    DAY = "day"
    MONTH = "month"
    YEAR = "year"


class RawReview(DomainModel):
    """A Review as a Source delivered it, before sanitizing. The text may be empty; it is untrusted data."""

    source: Source
    place_external_id: str = Field(min_length=1)
    external_id: str = Field(min_length=1)
    rating: Rating
    text: str
    published_on: date
    date_precision: DatePrecision
    language: str | None


class Review(DomainModel):
    """One public rating of a Place on a Source, with its text if it has one, without any personal data.

    A star-only Review has an empty text: it counts in Metrics but is never classified or shown to a model.
    """

    source: Source
    place_external_id: str = Field(min_length=1)
    external_id: str = Field(min_length=1)
    rating: Rating
    text: str = Field(pattern=r"^$|\S")
    published_on: date
    date_precision: DatePrecision
    language: str | None
    text_hash: str = Field(min_length=1)
    flagged: bool

    @property
    def has_text(self) -> bool:
        """Whether there is anything to classify or cite."""
        return bool(self.text)
