from collections.abc import Sequence
from datetime import date, timedelta

import pytest
from hypothesis import given
from hypothesis import strategies as st

from app.domain import (
    ChangeKind,
    DatePrecision,
    Review,
    ReviewTopic,
    Sentiment,
    Source,
)
from app.metrics import CHANGE_THRESHOLD, MIN_REVIEWS_PER_PERIOD, compute

GM = Source.GOOGLE_MAPS
FC = Source.FIRMY_CZ


def _review(
    external_id: str,
    rating: int,
    published_on: date,
    *,
    source: Source = GM,
    place: str = "p1",
    precision: DatePrecision = DatePrecision.DAY,
    flagged: bool = False,
) -> Review:
    return Review(
        source=source,
        place_external_id=place,
        external_id=external_id,
        rating=rating,
        text="text",
        published_on=published_on,
        date_precision=precision,
        language=None,
        text_hash=f"h-{external_id}",
        flagged=flagged,
    )


def _topic(review_id: str, key: str, sentiment: Sentiment) -> ReviewTopic:
    return ReviewTopic(review_external_id=review_id, topic_key=key, sentiment=sentiment, confidence=0.9)


def _month(
    prefix: str, month: int, ratings: Sequence[int], source: Source = GM, year: int = 2026
) -> list[Review]:
    """One Review per rating, on consecutive days of the month; ids are prefix0, prefix1, ..."""
    return [
        _review(f"{prefix}{i}", r, date(year, month, 10 + i), source=source) for i, r in enumerate(ratings)
    ]


def test_thresholds_are_named() -> None:
    assert CHANGE_THRESHOLD == 0.5
    assert MIN_REVIEWS_PER_PERIOD == 5


def test_empty_input_gives_empty_metrics() -> None:
    metrics = compute([], [])

    assert metrics.overall is None
    assert metrics.per_source == ()
    assert metrics.per_place == ()
    assert metrics.trend == ()
    assert metrics.topic_shares == ()
    assert metrics.changes == ()


def test_one_review_is_handled() -> None:
    metrics = compute([_review("a", 4, date(2026, 3, 15))], [])

    assert metrics.overall is not None
    assert (metrics.overall.average_rating, metrics.overall.count) == (4.0, 1)
    assert [(t.period_start, t.count) for t in metrics.trend] == [(date(2026, 3, 1), 1)]
    assert metrics.changes == ()


def test_overall_per_source_and_per_place_averages_and_counts() -> None:
    reviews = [
        _review("a", 5, date(2026, 3, 1), source=GM, place="g1"),
        _review("b", 4, date(2026, 3, 2), source=GM, place="g1"),
        _review("c", 3, date(2026, 3, 3), source=GM, place="g2"),
        _review("d", 2, date(2026, 3, 4), source=FC, place="f1"),
    ]

    metrics = compute(reviews, [])

    assert metrics.overall is not None
    assert (metrics.overall.average_rating, metrics.overall.count) == (3.5, 4)
    per_source = {s.source: (s.summary.average_rating, s.summary.count) for s in metrics.per_source}
    assert per_source == {GM: (4.0, 3), FC: (2.0, 1)}
    per_place = {
        (p.source, p.place_external_id): (p.summary.average_rating, p.summary.count)
        for p in metrics.per_place
    }
    assert per_place == {(GM, "g1"): (4.5, 2), (GM, "g2"): (3.0, 1), (FC, "f1"): (2.0, 1)}


def test_flagged_reviews_are_left_out_of_everything() -> None:
    reviews = [_review("a", 5, date(2026, 3, 1)), _review("b", 1, date(2026, 3, 2), flagged=True)]

    metrics = compute(reviews, [_topic("b", "waiting", Sentiment.NEGATIVE)])

    assert metrics.overall is not None
    assert (metrics.overall.average_rating, metrics.overall.count) == (5.0, 1)
    assert metrics.topic_shares == ()


def test_all_reviews_flagged_is_empty() -> None:
    assert compute([_review("a", 1, date(2026, 3, 1), flagged=True)], []).overall is None


def test_trend_point_per_source_per_month_in_order() -> None:
    reviews = [
        _review("a", 5, date(2026, 4, 30), source=FC),
        _review("b", 3, date(2026, 3, 31)),
        _review("c", 4, date(2026, 3, 1)),
        _review("d", 2, date(2026, 4, 1)),
    ]

    trend = [(t.source, t.period_start, t.average_rating, t.count) for t in compute(reviews, []).trend]

    assert trend == [
        (FC, date(2026, 4, 1), 5.0, 1),
        (GM, date(2026, 3, 1), 3.5, 2),
        (GM, date(2026, 4, 1), 2.0, 1),
    ]


def test_month_precision_date_lands_in_its_own_month() -> None:
    reviews = [
        _review("a", 4, date(2026, 3, 1), precision=DatePrecision.MONTH),
        _review("b", 2, date(2026, 3, 31), precision=DatePrecision.MONTH),
    ]

    trend = compute(reviews, []).trend

    assert [(t.period_start, t.count) for t in trend] == [(date(2026, 3, 1), 2)]


def test_year_precision_counts_in_averages_but_not_in_the_timeline() -> None:
    reviews = [
        _review("a", 5, date(2026, 1, 1), precision=DatePrecision.YEAR),
        _review("b", 3, date(2026, 3, 5)),
    ]

    metrics = compute(reviews, [])

    assert metrics.overall is not None
    assert (metrics.overall.average_rating, metrics.overall.count) == (4.0, 2)
    assert [(t.period_start, t.count) for t in metrics.trend] == [(date(2026, 3, 1), 1)]


def test_trend_sentiment_is_positive_minus_negative_over_mentions() -> None:
    reviews = [_review("a", 5, date(2026, 3, 1)), _review("b", 1, date(2026, 3, 2))]
    topics = [
        _topic("a", "staff", Sentiment.POSITIVE),
        _topic("a", "price", Sentiment.POSITIVE),
        _topic("b", "staff", Sentiment.NEGATIVE),
        _topic("b", "waiting", Sentiment.NEUTRAL),
    ]

    assert compute(reviews, topics).trend[0].sentiment == 0.25


def test_trend_sentiment_without_topics_is_zero() -> None:
    assert compute([_review("a", 5, date(2026, 3, 1))], []).trend[0].sentiment == 0.0


def test_topic_shares_count_sentiments_per_topic() -> None:
    reviews = [_review(i, 4, date(2026, 3, 1)) for i in "abc"]
    topics = [
        _topic("a", "waiting", Sentiment.NEGATIVE),
        _topic("b", "waiting", Sentiment.NEGATIVE),
        _topic("c", "waiting", Sentiment.POSITIVE),
        _topic("c", "staff", Sentiment.NEUTRAL),
        _topic("ghost", "staff", Sentiment.POSITIVE),
    ]

    shares = {s.topic_key: (s.positive, s.neutral, s.negative) for s in compute(reviews, topics).topic_shares}

    assert shares == {"waiting": (1, 0, 2), "staff": (0, 1, 0)}


def test_a_drop_is_detected_with_its_main_negative_topic() -> None:
    reviews = _month("m", 3, [5, 5, 4, 4, 5]) + _month("a", 4, [3, 3, 2, 3, 2])  # 4.6 -> 2.6
    topics = [
        _topic("a0", "waiting", Sentiment.NEGATIVE),
        _topic("a1", "waiting", Sentiment.NEGATIVE),
        _topic("a2", "price", Sentiment.NEGATIVE),
        _topic("a0", "staff", Sentiment.POSITIVE),
        _topic("a1", "staff", Sentiment.POSITIVE),
        _topic("a3", "staff", Sentiment.POSITIVE),
        _topic("m0", "price", Sentiment.NEGATIVE),
        _topic("m1", "price", Sentiment.NEGATIVE),
        _topic("m2", "price", Sentiment.NEGATIVE),
    ]

    (change,) = compute(reviews, topics).changes

    assert change.kind is ChangeKind.DROP
    assert (change.source, change.period_start) == (GM, date(2026, 4, 1))
    assert change.delta == pytest.approx(-2.0)
    assert change.main_topic_key == "waiting"


def test_a_rise_is_detected_with_its_main_positive_topic() -> None:
    reviews = _month("m", 3, [2, 2, 3, 2, 3]) + _month("a", 4, [5, 5, 4, 5, 4])
    topics = [
        _topic("a0", "staff", Sentiment.POSITIVE),
        _topic("a1", "staff", Sentiment.POSITIVE),
        _topic("a1", "waiting", Sentiment.NEGATIVE),
        _topic("a2", "waiting", Sentiment.NEGATIVE),
        _topic("a3", "waiting", Sentiment.NEGATIVE),
    ]

    (change,) = compute(reviews, topics).changes

    assert change.kind is ChangeKind.RISE
    assert change.delta == pytest.approx(2.2)
    assert change.main_topic_key == "staff"


def test_main_topic_ties_go_to_the_smaller_key() -> None:
    reviews = _month("m", 3, [5] * 5) + _month("a", 4, [1] * 5)
    topics = [_topic("a0", "waiting", Sentiment.NEGATIVE), _topic("a1", "price", Sentiment.NEGATIVE)]

    (change,) = compute(reviews, topics).changes

    assert change.main_topic_key == "price"


def test_a_change_without_a_matching_topic_has_no_main_topic() -> None:
    reviews = _month("m", 3, [5] * 5) + _month("a", 4, [1] * 5)

    (change,) = compute(reviews, [_topic("a0", "staff", Sentiment.POSITIVE)]).changes

    assert change.main_topic_key is None


@pytest.mark.parametrize(("march", "april"), [(5, 1), (1, 5)])
def test_a_month_with_too_few_reviews_never_yields_a_change(march: int, april: int) -> None:
    few = MIN_REVIEWS_PER_PERIOD - 1

    assert (
        compute(_month("m", 3, [march] * MIN_REVIEWS_PER_PERIOD) + _month("a", 4, [april] * few), []).changes
        == ()
    )
    assert (
        compute(_month("m", 3, [march] * few) + _month("a", 4, [april] * MIN_REVIEWS_PER_PERIOD), []).changes
        == ()
    )


def test_a_delta_just_below_the_threshold_is_no_change() -> None:
    reviews = _month("m", 3, [5, 5, 5, 5, 5]) + _month("a", 4, [5, 5, 5, 4, 4])  # 5.0 -> 4.6

    assert compute(reviews, []).changes == ()


def test_a_delta_of_exactly_the_threshold_is_a_change() -> None:
    reviews = _month("m", 3, [4] * 10) + _month("a", 4, [3] * 5 + [4] * 5)  # 4.0 -> 3.5

    (change,) = compute(reviews, []).changes

    assert change.delta == pytest.approx(-CHANGE_THRESHOLD)


def test_changes_are_per_source() -> None:
    reviews = (
        _month("g", 3, [5] * 5)
        + _month("h", 4, [5] * 5)
        + _month("f", 3, [5] * 5, source=FC)
        + _month("i", 4, [1] * 5, source=FC)
    )

    (change,) = compute(reviews, []).changes

    assert change.source is FC


def test_a_gap_month_between_two_points_gives_no_change() -> None:
    assert compute(_month("m", 3, [5] * 5) + _month("j", 5, [1] * 5), []).changes == ()


def test_a_single_month_gives_no_change() -> None:
    assert compute(_month("m", 3, [5, 1, 5, 1, 5, 1]), []).changes == ()


def test_january_follows_december() -> None:
    reviews = _month("d", 12, [5] * 5, year=2025) + _month("j", 1, [1] * 5, year=2026)

    (change,) = compute(reviews, []).changes

    assert change.period_start == date(2026, 1, 1)


_review_strategy = st.builds(
    lambda i, rating, day, source, place, flagged: _review(
        f"r{i}",
        rating,
        date(2026, 1, 1) + timedelta(days=day),
        source=source,
        place=place,
        flagged=flagged,
    ),
    st.uuids().map(str),
    st.integers(min_value=1, max_value=5),
    st.integers(min_value=0, max_value=180),
    st.sampled_from([GM, FC]),
    st.sampled_from(["p1", "p2"]),
    st.booleans(),
)
_reviews = st.lists(_review_strategy, unique_by=lambda r: r.external_id, max_size=40)


@given(_reviews)
def test_counts_add_up_across_every_grouping(reviews: list[Review]) -> None:
    metrics = compute(reviews, [])
    kept = [r for r in reviews if not r.flagged]

    total = metrics.overall.count if metrics.overall else 0
    assert total == len(kept)
    assert sum(s.summary.count for s in metrics.per_source) == total
    assert sum(p.summary.count for p in metrics.per_place) == total
    assert sum(t.count for t in metrics.trend) == total


@given(_reviews)
def test_averages_match_the_mean_and_stay_within_the_ratings(reviews: list[Review]) -> None:
    metrics = compute(reviews, [])
    kept = [r.rating for r in reviews if not r.flagged]

    if not kept:
        assert metrics.overall is None
        return
    assert metrics.overall is not None
    assert metrics.overall.average_rating == pytest.approx(sum(kept) / len(kept))
    assert min(kept) <= metrics.overall.average_rating <= max(kept)
    for point in metrics.trend:
        assert 1 <= point.average_rating <= 5


@given(_reviews)
def test_a_change_never_rests_on_a_thin_month(reviews: list[Review]) -> None:
    metrics = compute(reviews, [])
    counts = {(t.source, t.period_start): t.count for t in metrics.trend}

    for change in metrics.changes:
        assert counts[(change.source, change.period_start)] >= MIN_REVIEWS_PER_PERIOD
        assert abs(change.delta) >= CHANGE_THRESHOLD - 1e-9
