from collections import Counter, defaultdict
from collections.abc import Sequence
from datetime import date

from app.domain import (
    Change,
    ChangeKind,
    DatePrecision,
    Metrics,
    PlaceSummary,
    RatingSummary,
    Review,
    ReviewTopic,
    Sentiment,
    Source,
    SourceSummary,
    TopicShare,
    TrendPoint,
)
from app.metrics._average import average_rating

CHANGE_THRESHOLD = 0.5
"""Smallest change of the monthly average rating, in stars, that is a drop or a rise."""

MIN_REVIEWS_PER_PERIOD = 5
"""Fewest Reviews a month needs, and the month before it, for a change to be reported."""

_Period = tuple[Source, date]


def compute(reviews: Sequence[Review], topics: Sequence[ReviewTopic]) -> Metrics:
    """Compute every number of the dashboard. Flagged Reviews are excluded.

    A Review dated only by year counts in the averages but has no month, so it is not on the timeline.
    A change compares a month with the calendar month right before it, in the same Source.
    """
    kept = [r for r in reviews if not r.flagged]
    ids = {r.external_id for r in kept}
    kept_topics = [t for t in topics if t.review_external_id in ids]

    timeline = [r for r in kept if r.date_precision is not DatePrecision.YEAR]
    by_period: dict[_Period, list[Review]] = defaultdict(list)
    for review in timeline:
        by_period[(review.source, _month_start(review.published_on))].append(review)
    topics_by_review: dict[str, list[ReviewTopic]] = defaultdict(list)
    for topic in kept_topics:
        topics_by_review[topic.review_external_id].append(topic)

    trend = tuple(
        _trend_point(period, group, topics_by_review)
        for period, group in sorted(by_period.items(), key=_by_period)
    )
    return Metrics(
        trend=trend,
        topic_shares=_topic_shares(kept_topics),
        changes=_changes(trend, by_period, topics_by_review),
        overall=_summary(kept) if kept else None,
        per_source=_per_source(kept),
        per_place=_per_place(kept),
    )


def _by_period(item: tuple[_Period, list[Review]]) -> tuple[str, date]:
    (source, start), _ = item
    return source.value, start


def _month_start(day: date) -> date:
    return day.replace(day=1)


def _previous_month(start: date) -> date:
    return date(start.year - 1, 12, 1) if start.month == 1 else date(start.year, start.month - 1, 1)


def _summary(reviews: Sequence[Review]) -> RatingSummary:
    return RatingSummary(average_rating=average_rating([r.rating for r in reviews]), count=len(reviews))


def _per_source(reviews: Sequence[Review]) -> tuple[SourceSummary, ...]:
    groups: dict[Source, list[Review]] = defaultdict(list)
    for review in reviews:
        groups[review.source].append(review)
    return tuple(
        SourceSummary(source=source, summary=_summary(group))
        for source, group in sorted(groups.items(), key=lambda item: item[0].value)
    )


def _per_place(reviews: Sequence[Review]) -> tuple[PlaceSummary, ...]:
    groups: dict[tuple[str, str], list[Review]] = defaultdict(list)
    for review in reviews:
        groups[(review.source.value, review.place_external_id)].append(review)
    return tuple(
        PlaceSummary(source=group[0].source, place_external_id=place, summary=_summary(group))
        for (_, place), group in sorted(groups.items())
    )


def _sentiment_counts(
    group: Sequence[Review], topics_by_review: dict[str, list[ReviewTopic]]
) -> Counter[Sentiment]:
    return Counter(t.sentiment for r in group for t in topics_by_review.get(r.external_id, ()))


def _trend_point(
    period: _Period, group: Sequence[Review], topics_by_review: dict[str, list[ReviewTopic]]
) -> TrendPoint:
    source, start = period
    counts = _sentiment_counts(group, topics_by_review)
    mentions = sum(counts.values())
    sentiment = (counts[Sentiment.POSITIVE] - counts[Sentiment.NEGATIVE]) / mentions if mentions else 0.0
    return TrendPoint(
        source=source,
        period_start=start,
        average_rating=average_rating([r.rating for r in group]),
        count=len(group),
        sentiment=sentiment,
    )


def _topic_shares(topics: Sequence[ReviewTopic]) -> tuple[TopicShare, ...]:
    counts: dict[str, Counter[Sentiment]] = defaultdict(Counter)
    for topic in topics:
        counts[topic.topic_key][topic.sentiment] += 1
    return tuple(
        TopicShare(
            topic_key=key,
            positive=c[Sentiment.POSITIVE],
            neutral=c[Sentiment.NEUTRAL],
            negative=c[Sentiment.NEGATIVE],
        )
        for key, c in sorted(counts.items())
    )


def _changes(
    trend: Sequence[TrendPoint],
    by_period: dict[_Period, list[Review]],
    topics_by_review: dict[str, list[ReviewTopic]],
) -> tuple[Change, ...]:
    points = {(p.source, p.period_start): p for p in trend}
    changes: list[Change] = []
    for point in trend:
        previous = points.get((point.source, _previous_month(point.period_start)))
        if previous is None or min(point.count, previous.count) < MIN_REVIEWS_PER_PERIOD:
            continue
        delta = round(point.average_rating - previous.average_rating, 9)
        if abs(delta) < CHANGE_THRESHOLD:
            continue
        kind = ChangeKind.DROP if delta < 0 else ChangeKind.RISE
        group = by_period[(point.source, point.period_start)]
        changes.append(
            Change(
                kind=kind,
                source=point.source,
                period_start=point.period_start,
                delta=delta,
                main_topic_key=_main_topic(kind, group, topics_by_review),
            )
        )
    return tuple(changes)


def _main_topic(
    kind: ChangeKind, group: Sequence[Review], topics_by_review: dict[str, list[ReviewTopic]]
) -> str | None:
    """The Topic most mentioned with the sentiment that explains the change; ties go to the smaller key."""
    wanted = Sentiment.NEGATIVE if kind is ChangeKind.DROP else Sentiment.POSITIVE
    counts = Counter(
        t.topic_key for r in group for t in topics_by_review.get(r.external_id, ()) if t.sentiment is wanted
    )
    if not counts:
        return None
    return min(counts, key=lambda key: (-counts[key], key))
