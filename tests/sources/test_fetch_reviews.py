import json
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import SecretStr

from app.domain import DatePrecision, FakeClock, Place, RawReview, Source
from app.gateway import (
    SCRAPE_GOOGLE_REVIEWS,
    ApifyClient,
    BudgetExceeded,
    ClientError,
    ClientResponse,
    FakeCallLog,
    FakeServiceClient,
    Gateway,
    GatewayConfig,
    GatewayDenied,
    ReviewScrape,
    ScrapedReview,
    ServicePolicy,
    Units,
)
from app.sources import Sources
from app.transport import FakeTransport, HttpResponse

FIXTURE = Path(__file__).parents[1] / "fixtures/sources/google_maps/2026-11-13-camp-velo.json"
PLACE = Place(
    source=Source.GOOGLE_MAPS,
    external_id="ChIJcYfUFDm1ckcRizeMvL_POzQ",
    name="CAMP VELO",
    address="Vratěnín",
)
RUN = "run-1"
START = datetime(2026, 11, 13, 18, 0, tzinfo=UTC)


def scraped(index: int, day: date, stars: int = 5, text: str | None = None) -> ScrapedReview:
    return ScrapedReview(
        PLACE.external_id,
        f"id{index}",
        stars,
        f"Text {index}" if text is None else text,
        datetime(day.year, day.month, day.day, 10, 0, tzinfo=UTC),
        "cs",
    )


def sources(client: FakeServiceClient | ApifyClient, run_cap: str = "5") -> tuple[Sources, FakeCallLog]:
    log = FakeCallLog()
    policy = ServicePolicy(frozenset({SCRAPE_GOOGLE_REVIEWS}), 10, timedelta(seconds=60), 2)
    config = GatewayConfig({"apify": policy}, Decimal(run_cap))
    return Sources(Gateway(config, {"apify": client}, FakeClock(START), log)), log


def scripted(*reviews: ScrapedReview) -> FakeServiceClient:
    def respond(_operation: str, request: object) -> ClientResponse:
        assert isinstance(request, ReviewScrape)
        return ClientResponse(tuple(reviews), Units("apify", "review", len(reviews)))

    return FakeServiceClient(Units("apify", "review", 1), respond)


def test_a_review_becomes_a_raw_review_with_an_exact_day() -> None:
    adapter, _ = sources(scripted(scraped(1, date(2026, 10, 30), stars=3, text="Špatná obsluha")))
    assert adapter.fetch_reviews(PLACE, None, 10, run_id=RUN) == [
        RawReview(
            source=Source.GOOGLE_MAPS,
            place_external_id=PLACE.external_id,
            external_id="id1",
            rating=3,
            text="Špatná obsluha",
            published_on=date(2026, 10, 30),
            date_precision=DatePrecision.DAY,
            language="cs",
        )
    ]


def test_the_newest_reviews_come_first_and_the_limit_cuts_the_rest() -> None:
    answer = scripted(
        scraped(1, date(2026, 9, 1)), scraped(2, date(2026, 10, 5)), scraped(3, date(2026, 8, 1))
    )
    adapter, _ = sources(answer)
    result = adapter.fetch_reviews(PLACE, None, 2, run_id=RUN)
    assert [r.external_id for r in result] == ["id2", "id1"]


def test_fewer_reviews_than_the_limit_is_a_partial_result_not_an_error() -> None:
    adapter, _ = sources(scripted(scraped(1, date(2026, 9, 1)), scraped(2, date(2026, 9, 2))))
    assert len(adapter.fetch_reviews(PLACE, None, 100, run_id=RUN)) == 2


def test_an_empty_result_is_an_empty_list() -> None:
    adapter, log = sources(scripted())
    assert adapter.fetch_reviews(PLACE, None, 10, run_id=RUN) == []
    assert [call.status for call in log.calls] == ["ok"]


def test_since_is_inclusive_and_older_reviews_are_dropped_even_when_the_actor_returns_them() -> None:
    answer = scripted(
        scraped(1, date(2026, 10, 1)), scraped(2, date(2026, 9, 30)), scraped(3, date(2026, 10, 2))
    )
    adapter, _ = sources(answer)
    result = adapter.fetch_reviews(PLACE, date(2026, 10, 1), 10, run_id=RUN)
    assert [r.external_id for r in result] == ["id3", "id1"]


def test_since_and_limit_are_passed_to_the_actor_request() -> None:
    client = scripted()
    adapter, _ = sources(client)
    adapter.fetch_reviews(PLACE, date(2026, 10, 1), 40, run_id=RUN)
    assert client.calls == [(SCRAPE_GOOGLE_REVIEWS, ReviewScrape(PLACE.external_id, date(2026, 10, 1), 40))]


def test_a_review_delivered_twice_is_returned_once() -> None:
    adapter, _ = sources(scripted(scraped(1, date(2026, 9, 1)), scraped(1, date(2026, 9, 1))))
    assert len(adapter.fetch_reviews(PLACE, None, 10, run_id=RUN)) == 1


def test_a_review_without_text_is_kept() -> None:
    adapter, _ = sources(scripted(scraped(1, date(2026, 9, 1), text="")))
    assert adapter.fetch_reviews(PLACE, None, 10, run_id=RUN)[0].text == ""


def test_the_date_is_the_utc_day_of_the_timestamp() -> None:
    late = ScrapedReview(PLACE.external_id, "x", 4, "t", datetime(2026, 10, 30, 23, 59, tzinfo=UTC), None)
    adapter, _ = sources(scripted(late))
    review = adapter.fetch_reviews(PLACE, None, 10, run_id=RUN)[0]
    assert (review.published_on, review.language) == (date(2026, 10, 30), None)


def test_a_place_of_another_source_is_refused_before_any_call() -> None:
    client = scripted()
    adapter, log = sources(client)
    firmy = Place(source=Source.FIRMY_CZ, external_id="13502193", name="Camp Velo", address="")
    with pytest.raises(ValueError, match="firmy_cz"):
        adapter.fetch_reviews(firmy, None, 10, run_id=RUN)
    assert client.calls == [] and log.calls == []


@pytest.mark.parametrize("limit", [0, -5])
def test_a_limit_below_one_is_refused(limit: int) -> None:
    adapter, _ = sources(scripted())
    with pytest.raises(ValueError, match="limit"):
        adapter.fetch_reviews(PLACE, None, limit, run_id=RUN)


def test_the_budget_is_reserved_for_the_limit_before_the_run_starts() -> None:
    transport = FakeTransport()
    adapter, log = sources(ApifyClient(SecretStr("token"), transport), run_cap="0.01")
    with pytest.raises(BudgetExceeded):  # 0.0006 USD per Review: 100 Reviews is 0.06 USD
        adapter.fetch_reviews(PLACE, None, 100, run_id=RUN)
    assert transport.requests == []
    assert [call.status for call in log.calls] == ["denied"]


def test_the_cost_booked_is_for_the_reviews_actually_returned() -> None:
    adapter, log = sources(scripted(scraped(1, date(2026, 9, 1)), scraped(2, date(2026, 9, 2))))
    adapter.fetch_reviews(PLACE, None, 100, run_id=RUN)
    assert log.calls[0].cost == Decimal("0.0012")


def test_a_denied_call_and_a_provider_failure_reach_the_caller() -> None:
    denied = Sources(Gateway(GatewayConfig({}, Decimal(5)), {}, FakeClock(START), FakeCallLog()))
    with pytest.raises(GatewayDenied):
        denied.fetch_reviews(PLACE, None, 10, run_id=RUN)

    def fail(_operation: str, _request: object) -> ClientResponse:
        raise ClientError("schema_changed")

    adapter, _ = sources(FakeServiceClient(Units("apify", "review", 1), fail))
    with pytest.raises(ClientError, match="schema_changed"):
        adapter.fetch_reviews(PLACE, None, 10, run_id=RUN)


def test_the_recorded_google_maps_run_goes_through_the_whole_chain() -> None:
    transport = FakeTransport(HttpResponse(200, FIXTURE.read_bytes()))
    adapter, log = sources(ApifyClient(SecretStr("token"), transport))
    result = adapter.fetch_reviews(PLACE, None, 20, run_id=RUN)
    assert len(result) == 20
    assert result[0].external_id.startswith("Ci9DQUlRQUNvZENodHljRjlvT201R09E")
    assert all(r.source is Source.GOOGLE_MAPS and r.place_external_id == PLACE.external_id for r in result)
    assert [r.published_on for r in result] == sorted((r.published_on for r in result), reverse=True)
    assert log.calls[0].units == 20 and log.calls[0].service == "apify"
    assert json.loads(transport.requests[0].body)["maxReviews"] == 20
