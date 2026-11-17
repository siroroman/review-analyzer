from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from app.domain import FakeClock, Place, PlaceDetails, Source
from app.gateway import (
    GET_PLACE_DETAILS,
    ClientError,
    ClientResponse,
    FakeCallLog,
    FakeServiceClient,
    Gateway,
    GatewayConfig,
    GatewayDenied,
    PlaceDetailsLookup,
    ServicePolicy,
    Units,
)
from app.sources import PlaceDetailsSource

PLACE = Place(source=Source.GOOGLE_MAPS, external_id="ChIJ1", name="Alza", address="Praha 7")
RUN = "run-1"
DETAILS = PlaceDetails(rating=4.3, review_count=26348)
ONE_PLACE = Units("gosom", "place", 1)


def source(
    client: FakeServiceClient, operations: frozenset[str] = frozenset({GET_PLACE_DETAILS})
) -> tuple[PlaceDetailsSource, FakeCallLog]:
    log = FakeCallLog()
    config = GatewayConfig({"gosom": ServicePolicy(operations, 10, timedelta(seconds=60), 2)}, Decimal(5))
    clock = FakeClock(datetime(2026, 11, 17, 10, 0, tzinfo=UTC))
    return PlaceDetailsSource(Gateway(config, {"gosom": client}, clock, log)), log


def answering(payload: object = DETAILS) -> FakeServiceClient:
    return FakeServiceClient(ONE_PLACE, lambda _op, _req: ClientResponse(payload, ONE_PLACE))


def test_the_details_of_a_google_place_come_back_through_the_gateway() -> None:
    client = answering()
    adapter, log = source(client)

    assert adapter.fetch_place_details(PLACE, run_id=RUN) == DETAILS
    assert client.calls == [(GET_PLACE_DETAILS, PlaceDetailsLookup("ChIJ1"))]
    (call,) = log.calls
    assert (call.service, call.operation, call.run_id, call.status, call.cost) == (
        "gosom",
        GET_PLACE_DETAILS,
        RUN,
        "ok",
        Decimal(0),
    )


def test_a_place_of_another_source_is_refused_before_any_call() -> None:
    client = answering()
    adapter, _ = source(client)
    firmy = Place(source=Source.FIRMY_CZ, external_id="1", name="Alza", address="Praha")

    with pytest.raises(ValueError, match="firmy_cz"):
        adapter.fetch_place_details(firmy, run_id=RUN)
    assert client.calls == []


def test_a_service_off_the_allow_list_is_denied() -> None:
    adapter, _ = source(answering(), operations=frozenset({"other"}))

    with pytest.raises(GatewayDenied):
        adapter.fetch_place_details(PLACE, run_id=RUN)


def test_a_failure_of_the_client_passes_through() -> None:
    def fail(_op: str, _req: object) -> ClientResponse:
        raise ClientError("not_found")

    adapter, _ = source(FakeServiceClient(ONE_PLACE, fail))

    with pytest.raises(ClientError) as raised:
        adapter.fetch_place_details(PLACE, run_id=RUN)
    assert raised.value.kind == "not_found"


def test_an_answer_that_is_not_details_is_a_bad_response() -> None:
    adapter, _ = source(answering("nonsense"))

    with pytest.raises(ClientError) as raised:
        adapter.fetch_place_details(PLACE, run_id=RUN)
    assert raised.value.kind == "bad_response"
