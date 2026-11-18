import json
from collections.abc import Sequence
from datetime import date

from app.domain import DatePrecision, Review, Source, Taxonomy, Topic
from app.llm import Route
from app.storage import StoredTaxonomy
from app.taxonomy import UNCLASSIFIED_KEY
from tests.llm.helpers import JEV, JEV_USAGE, Setup, Step, requests, scripted

ROUTES = {"classification": Route(JEV)}
PLACE = "g1"


def taxonomy(version: int = 1) -> StoredTaxonomy:
    topics = (
        Topic(key="staff", name="Obsluha", description="How staff treat guests"),
        Topic(key="waiting", name="Čekání", description="How long things take"),
        Topic(key="prices", name="Ceny", description="Value for money"),
        Topic(key=UNCLASSIFIED_KEY, name="Nezařazeno", description="Fits none of the others"),
    )
    return StoredTaxonomy(version, Taxonomy(industry="cafe", topics=topics))


def review(index: int, text: str | None = None, flagged: bool = False) -> Review:
    return Review(
        source=Source.GOOGLE_MAPS,
        place_external_id=PLACE,
        external_id=f"r{index:03d}",
        rating=4,
        text=text or f"Recenze číslo {index}",
        published_on=date(2026, 10, 1),
        date_precision=DatePrecision.DAY,
        language="cs",
        text_hash=f"h{index}",
        flagged=flagged,
    )


def answer(**asked: float | tuple[float, str]) -> str:
    """What Jev answers for one Review: a score and a sentiment for every Topic of `taxonomy()`.

    A Topic given as a number gets a positive sentiment, as `(score, sentiment)` its own; a Topic left out
    scores 0.
    """
    fields: dict[str, object] = {}
    for key in ("staff", "waiting", "prices"):
        value = asked.get(key, (0, "neutral"))
        score, sentiment = value if isinstance(value, tuple) else (value, "positive")
        fields[f"topic_{key}"] = score
        fields[f"sentiment_{key}"] = sentiment
    return json.dumps(fields)


def setup(jev: Sequence[Step], routes: dict[str, Route] | None = None, run_cap: str = "5") -> Setup:
    return Setup(
        jev=lambda clock: scripted(JEV_USAGE, *jev, clock=clock),
        routes=routes or ROUTES,
        run_cap=run_cap,
    )


__all__ = ["requests"]
