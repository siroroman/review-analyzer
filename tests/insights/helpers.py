import json
from datetime import date

from app.domain import (
    Change,
    ChangeKind,
    DatePrecision,
    Metrics,
    RatingSummary,
    Review,
    Source,
    TopicShare,
    TrendPoint,
)
from app.insights import FakeCompleter, InsightGenerator

RUN = "run-1"


def review(external_id: str, text: str = "Čekali jsme hodinu.", *, flagged: bool = False) -> Review:
    return Review(
        source=Source.GOOGLE_MAPS,
        place_external_id="p1",
        external_id=external_id,
        rating=2,
        text=text,
        published_on=date(2026, 10, 3),
        date_precision=DatePrecision.DAY,
        language="cs",
        text_hash=f"hash-{external_id}",
        flagged=flagged,
    )


def metrics() -> Metrics:
    return Metrics(
        trend=(
            TrendPoint(
                source=Source.GOOGLE_MAPS,
                period_start=date(2026, 10, 1),
                average_rating=3.0,
                count=10,
                sentiment=-0.2,
            ),
        ),
        topic_shares=(TopicShare(topic_key="waiting", positive=1, neutral=2, negative=7),),
        changes=(
            Change(
                kind=ChangeKind.DROP,
                source=Source.GOOGLE_MAPS,
                period_start=date(2026, 10, 1),
                delta=-0.8,
                main_topic_key="waiting",
            ),
        ),
        overall=RatingSummary(average_rating=3.4, count=10),
    )


def item(text: str, ids: list[str], kind: str = "summary") -> dict[str, object]:
    return {
        "type": kind,
        "period_start": "2026-10-01",
        "period_end": "2026-10-31",
        "text": text,
        "review_ids": ids,
    }


def answer(*items: dict[str, object]) -> str:
    return json.dumps({"insights": list(items)})


def setup(*steps: str | Exception) -> tuple[InsightGenerator, FakeCompleter]:
    completer = FakeCompleter(*steps)
    return InsightGenerator(completer), completer
