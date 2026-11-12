from datetime import date
from enum import StrEnum

from pydantic import Field, model_validator

from app.domain._base import DomainModel
from app.domain._places import Source


class TrendPoint(DomainModel):
    """The average rating, count and sentiment of one Source in one period; a point of the timeline."""

    source: Source
    period_start: date
    average_rating: float = Field(ge=1, le=5, allow_inf_nan=False)
    count: int = Field(ge=0)
    sentiment: float = Field(ge=-1, le=1, allow_inf_nan=False)


class TopicShare(DomainModel):
    """How many mentions of one Topic were positive, neutral and negative."""

    topic_key: str = Field(min_length=1)
    positive: int = Field(ge=0)
    neutral: int = Field(ge=0)
    negative: int = Field(ge=0)


class RatingSummary(DomainModel):
    """The average rating and the number of Reviews of one group (all, one Source or one Place)."""

    average_rating: float = Field(ge=1, le=5, allow_inf_nan=False)
    count: int = Field(ge=1)


class SourceSummary(DomainModel):
    """The RatingSummary of one Source."""

    source: Source
    summary: RatingSummary


class PlaceSummary(DomainModel):
    """The RatingSummary of one Place, for the comparison of Places."""

    source: Source
    place_external_id: str = Field(min_length=1)
    summary: RatingSummary


class ChangeKind(StrEnum):
    DROP = "drop"
    RISE = "rise"


class Change(DomainModel):
    """A detected drop or rise of the average rating of one Source in one period."""

    kind: ChangeKind
    source: Source
    period_start: date
    delta: float = Field(allow_inf_nan=False)
    main_topic_key: str | None = None

    @model_validator(mode="after")
    def _delta_matches_kind(self) -> "Change":
        if self.kind is ChangeKind.DROP and self.delta >= 0:
            raise ValueError("a drop has a negative delta")
        if self.kind is ChangeKind.RISE and self.delta <= 0:
            raise ValueError("a rise has a positive delta")
        return self


class Metrics(DomainModel):
    """Everything computed by code from Reviews and ReviewTopics."""

    trend: tuple[TrendPoint, ...]
    topic_shares: tuple[TopicShare, ...]
    changes: tuple[Change, ...]
    overall: RatingSummary | None = None
    per_source: tuple[SourceSummary, ...] = ()
    per_place: tuple[PlaceSummary, ...] = ()


class InsightType(StrEnum):
    SUMMARY = "summary"
    ANOMALY = "anomaly"
    SUGGESTION = "suggestion"


class Insight(DomainModel):
    """A statement by the strong model that cites the IDs of the Reviews it rests on."""

    type: InsightType
    period_start: date
    period_end: date
    text: str = Field(min_length=1, pattern=r"\S")
    review_ids: tuple[str, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _period_is_ordered(self) -> "Insight":
        if self.period_end < self.period_start:
            raise ValueError("an Insight period does not end before it starts")
        return self
