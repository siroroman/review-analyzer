import pytest
from hypothesis import given
from hypothesis import strategies as st
from pydantic import ValidationError

from app.domain import ReviewTopic, Sentiment, Taxonomy, Topic


def _topic(key: str = "waiting") -> Topic:
    return Topic(key=key, name="Čekání", description="Jak dlouho zákazník čeká.")


def test_taxonomy_round_trips_through_json() -> None:
    taxonomy = Taxonomy(industry="retail", topics=(_topic("waiting"), _topic("prices")))

    assert Taxonomy.model_validate_json(taxonomy.model_dump_json()) == taxonomy


def test_taxonomy_rejects_a_duplicate_topic_key() -> None:
    with pytest.raises(ValidationError):
        Taxonomy(industry="retail", topics=(_topic("waiting"), _topic("waiting")))


def test_taxonomy_rejects_no_topics() -> None:
    with pytest.raises(ValidationError):
        Taxonomy(industry="retail", topics=())


def test_topic_rejects_an_empty_key() -> None:
    with pytest.raises(ValidationError):
        _topic(key="")


def test_review_topic_round_trips_through_json() -> None:
    assignment = ReviewTopic(
        review_external_id="rev-1", topic_key="waiting", sentiment=Sentiment.NEGATIVE, confidence=0.8
    )

    assert ReviewTopic.model_validate_json(assignment.model_dump_json()) == assignment
    assert assignment.model_dump(mode="json")["sentiment"] == "negative"


@given(confidence=st.floats(min_value=0, max_value=1))
def test_review_topic_accepts_confidence_from_zero_to_one(confidence: float) -> None:
    assignment = ReviewTopic(
        review_external_id="r", topic_key="t", sentiment=Sentiment.POSITIVE, confidence=confidence
    )

    assert assignment.confidence == confidence


@pytest.mark.parametrize("confidence", [-0.01, 1.01, float("nan"), float("inf")])
def test_review_topic_rejects_confidence_outside_zero_to_one(confidence: float) -> None:
    with pytest.raises(ValidationError):
        ReviewTopic(review_external_id="r", topic_key="t", sentiment=Sentiment.NEUTRAL, confidence=confidence)


def test_review_topic_rejects_an_unknown_sentiment() -> None:
    with pytest.raises(ValidationError):
        ReviewTopic.model_validate(
            {"review_external_id": "r", "topic_key": "t", "sentiment": "angry", "confidence": 0.5}
        )
