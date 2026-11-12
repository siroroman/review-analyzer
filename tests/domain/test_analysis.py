from datetime import date

import pytest
from hypothesis import given
from hypothesis import strategies as st
from pydantic import ValidationError

from app.domain import (
    Change,
    ChangeKind,
    Insight,
    InsightType,
    Metrics,
    Source,
    TopicShare,
    TrendPoint,
)


def _point(**changes: object) -> TrendPoint:
    fields: dict[str, object] = {
        "source": Source.GOOGLE_MAPS,
        "period_start": date(2026, 3, 1),
        "average_rating": 4.25,
        "count": 12,
        "sentiment": 0.4,
    }
    return TrendPoint.model_validate(fields | changes)


def _insight(**changes: object) -> Insight:
    fields: dict[str, object] = {
        "type": InsightType.ANOMALY,
        "period_start": date(2026, 3, 1),
        "period_end": date(2026, 3, 31),
        "text": "Hodnocení kleslo kvůli čekání u pokladny.",
        "review_ids": ("rev-1", "rev-2"),
    }
    return Insight.model_validate(fields | changes)


def test_trend_point_round_trips_through_json() -> None:
    point = _point()

    assert TrendPoint.model_validate_json(point.model_dump_json()) == point


@given(average=st.floats(min_value=1, max_value=5))
def test_trend_point_accepts_an_average_between_one_and_five(average: float) -> None:
    assert _point(average_rating=average).average_rating == average


@pytest.mark.parametrize("average", [0.99, 5.01, float("nan")])
def test_trend_point_rejects_an_average_outside_one_to_five(average: float) -> None:
    with pytest.raises(ValidationError):
        _point(average_rating=average)


def test_trend_point_rejects_a_negative_count() -> None:
    with pytest.raises(ValidationError):
        _point(count=-1)


@pytest.mark.parametrize("sentiment", [-1.01, 1.01])
def test_trend_point_rejects_sentiment_outside_minus_one_to_one(sentiment: float) -> None:
    with pytest.raises(ValidationError):
        _point(sentiment=sentiment)


def test_metrics_round_trips_through_json() -> None:
    metrics = Metrics(
        trend=(_point(),),
        topic_shares=(TopicShare(topic_key="waiting", positive=3, neutral=1, negative=8),),
        changes=(
            Change(
                kind=ChangeKind.DROP,
                source=Source.GOOGLE_MAPS,
                period_start=date(2026, 3, 1),
                delta=-0.8,
            ),
        ),
    )

    assert Metrics.model_validate_json(metrics.model_dump_json()) == metrics


def test_topic_share_rejects_a_negative_count() -> None:
    with pytest.raises(ValidationError):
        TopicShare(topic_key="waiting", positive=-1, neutral=0, negative=0)


def test_change_rejects_a_drop_with_a_positive_delta() -> None:
    with pytest.raises(ValidationError):
        Change(kind=ChangeKind.DROP, source=Source.FIRMY_CZ, period_start=date(2026, 3, 1), delta=0.5)


def test_change_rejects_a_rise_with_a_negative_delta() -> None:
    with pytest.raises(ValidationError):
        Change(kind=ChangeKind.RISE, source=Source.FIRMY_CZ, period_start=date(2026, 3, 1), delta=-0.5)


def test_insight_round_trips_through_json() -> None:
    insight = _insight()

    assert Insight.model_validate_json(insight.model_dump_json()) == insight
    assert insight.model_dump(mode="json")["type"] == "anomaly"


def test_insight_needs_at_least_one_review_id() -> None:
    with pytest.raises(ValidationError):
        _insight(review_ids=())


def test_insight_rejects_empty_text() -> None:
    with pytest.raises(ValidationError):
        _insight(text="  ")


def test_insight_rejects_a_period_that_ends_before_it_starts() -> None:
    with pytest.raises(ValidationError):
        _insight(period_start=date(2026, 4, 1), period_end=date(2026, 3, 1))
