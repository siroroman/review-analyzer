import json
from datetime import date

from app.domain import DatePrecision, Review, Source, Taxonomy, Topic
from app.llm import ModelRef, Route
from app.storage import StoredTaxonomy
from app.taxonomy import UNCLASSIFIED_KEY
from tests.llm.helpers import HAIKU_USAGE, JEV, JEV_USAGE, Setup, Step, requests, scripted

HAIKU = ModelRef("anthropic", "claude-haiku")
ROUTES = {"classification": Route(JEV, HAIKU)}
PLACE = "g1"


def taxonomy(version: int = 1) -> StoredTaxonomy:
    topics = (
        Topic(key="staff", name="Staff", description="How staff treat guests"),
        Topic(key="waiting", name="Waiting", description="How long things take"),
        Topic(key="prices", name="Prices", description="Value for money"),
        Topic(key=UNCLASSIFIED_KEY, name="Unclassified", description="Fits none of the others"),
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


def entry(rid: str, *topics: tuple[str, str, float]) -> dict[str, object]:
    return {
        "id": rid,
        "topics": [
            {"key": key, "sentiment": sentiment, "confidence": conf} for key, sentiment, conf in topics
        ],
    }


def answer(*entries: dict[str, object]) -> str:
    return json.dumps({"results": list(entries)})


def full_answer(count: int, key: str = "staff") -> str:
    """Every Review of a batch of `count` gets one positive Topic."""
    return answer(*(entry(str(i), (key, "positive", 0.9)) for i in range(1, count + 1)))


def setup(
    jev: list[Step],
    haiku: list[Step] | None = None,
    routes: dict[str, Route] | None = None,
    run_cap: str = "5",
) -> Setup:
    return Setup(
        jev=lambda clock: scripted(JEV_USAGE, *jev, clock=clock),
        haiku=lambda clock: scripted(HAIKU_USAGE, *(haiku or []), clock=clock),
        routes=routes or ROUTES,
        run_cap=run_cap,
    )


__all__ = ["requests"]
