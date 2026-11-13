from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from app.domain import Company, DatePrecision, Place, Review, Source
from app.gateway import CallStatus, ServiceCall

START = datetime(2026, 11, 12, 8, 0, tzinfo=UTC)


def place(external_id: str = "g1", source: Source = Source.GOOGLE_MAPS, name: str = "Praha 1") -> Place:
    return Place(source=source, external_id=external_id, name=name, address="Hlavní 1, Praha")


def company(*places: Place, name: str = "Kavárna") -> Company:
    return Company(name=name, industry="cafe", places=places or (place(),))


def review(
    external_id: str = "r1",
    place_external_id: str = "g1",
    source: Source = Source.GOOGLE_MAPS,
    published_on: date = date(2026, 10, 1),
    flagged: bool = False,
) -> Review:
    return Review(
        source=source,
        place_external_id=place_external_id,
        external_id=external_id,
        rating=4,
        text="Dobrá káva, pomalá obsluha.",
        published_on=published_on,
        date_precision=DatePrecision.DAY,
        language="cs",
        text_hash=f"hash-{external_id}",
        flagged=flagged,
    )


def call(
    service: str = "apify",
    operation: str = "run_actor",
    run_id: str = "run-1",
    status: CallStatus = "ok",
    cost: str = "0.5",
    at: datetime = START,
) -> ServiceCall:
    return ServiceCall(
        service=service,
        operation=operation,
        run_id=run_id,
        status=status,
        cost=Decimal(cost),
        unit="items",
        units=10,
        latency=timedelta(milliseconds=250),
        error_kind=None if status == "ok" else "boom",
        at=at,
    )
