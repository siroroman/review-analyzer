"""Shared vocabulary and ports without an external service behind them (ADR-0002)."""

from app.domain._analysis import (
    Change,
    ChangeKind,
    Insight,
    InsightType,
    Metrics,
    TopicShare,
    TrendPoint,
)
from app.domain._clock import Clock, FakeClock
from app.domain._places import Company, Place, Source
from app.domain._reviews import DatePrecision, Rating, RawReview, Review
from app.domain._run_status import InvalidTransition, RunStatus, advance
from app.domain._topics import ReviewTopic, Sentiment, Taxonomy, Topic

__all__ = [
    "InvalidTransition",
    "RunStatus",
    "advance",
    "Change",
    "ChangeKind",
    "Insight",
    "InsightType",
    "Metrics",
    "TopicShare",
    "TrendPoint",
    "Clock",
    "Company",
    "DatePrecision",
    "FakeClock",
    "Place",
    "Rating",
    "RawReview",
    "Review",
    "ReviewTopic",
    "Sentiment",
    "Taxonomy",
    "Topic",
    "Source",
]
