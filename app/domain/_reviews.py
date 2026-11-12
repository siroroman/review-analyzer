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
    """One public rating with text and date of a Place on a Source, without any personal data."""

    source: Source
    place_external_id: str = Field(min_length=1)
    external_id: str = Field(min_length=1)
    rating: Rating
    text: str = Field(min_length=1, pattern=r"\S")
    published_on: date
    date_precision: DatePrecision
    language: str | None
    text_hash: str = Field(min_length=1)
    flagged: bool
