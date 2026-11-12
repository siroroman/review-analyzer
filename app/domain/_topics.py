from enum import StrEnum

from pydantic import Field, model_validator

from app.domain._base import DomainModel


class Sentiment(StrEnum):
    """How a Review speaks about a Topic."""

    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"


class Topic(DomainModel):
    """A subject reviews talk about (e.g. staff, waiting, prices), part of a Taxonomy."""

    key: str = Field(min_length=1)
    name: str = Field(min_length=1)
    description: str


class Taxonomy(DomainModel):
    """The frozen list of Topics for one industry."""

    industry: str = Field(min_length=1)
    topics: tuple[Topic, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _keys_are_unique(self) -> "Taxonomy":
        if len({topic.key for topic in self.topics}) != len(self.topics):
            raise ValueError("a Taxonomy lists each Topic key once")
        return self


class ReviewTopic(DomainModel):
    """The assignment of one Topic to one Review with a sentiment and a confidence."""

    review_external_id: str = Field(min_length=1)
    topic_key: str = Field(min_length=1)
    sentiment: Sentiment
    confidence: float = Field(ge=0, le=1, allow_inf_nan=False)
