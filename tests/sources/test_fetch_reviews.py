import json
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from app.domain import DatePrecision, FakeClock, Place, RawReview, Source
from app.gateway import (
    SCRAPE_GOOGLE_REVIEWS,
    ClientError,
    ClientResponse,
    FakeCallLog,
    FakeServiceClient,
    Gateway,
    GatewayConfig,
    GatewayDenied,
    ScrapedReview,
    ServicePolicy,
    Units,
    YasogaNClient,
    YasogaNScrape,
)
from app.sources import Sources
from app.transport import FakeTransport, HttpResponse

FIXTURE = Path(__file__).parents[1] / "fixtures/sources/google_maps/2026-11-17-yasogan-sample.json"
PLACE = Place(
    source=Source.GOOGLE_MAPS,
    external_id="ChIJcYfUFDm1ckcRizeMvL_POzQ",
    name="CAMP VELO",
    address="Vratěnín",
)
RUN = "run-1"
START = datetime(2026, 11, 17, 18, 0, tzinfo=UTC)


def scraped(index: int, day: date, stars: int = 5, text: str | None = None, hour: int = 10) -> ScrapedReview:
    return ScrapedReview(
        f"id{index}",
        stars,
        f"Text {index}" if text is None else text,
        datetime(day.year, day.month, day.day, hour, 0, tzinfo=UTC),
    )


def sources(client: FakeServiceClient | YasogaNClient, run_cap: str = "5") -> tuple[Sources, FakeCallLog]:
    log = FakeCallLog()
    policy = ServicePolicy(frozenset({SCRAPE_GOOGLE_REVIEWS}), 10, timedelta(seconds=60), 2)
    config = GatewayConfig({"yasogan": policy}, Decimal(run_cap))
    return Sources(Gateway(config, {"yasogan": client}, FakeClock(START), log)), log


def scripted(*reviews: ScrapedReview) -> FakeServiceClient:
    def respond(_operation: str, request: object) -> ClientResponse:
        assert isinstance(request, YasogaNScrape)
        return ClientResponse(tuple(reviews), Units("yasogan", "review", len(reviews)))

    return FakeServiceClient(Units("yasogan", "review", 1), respond)


def test_a_review_becomes_a_raw_review_with_an_exact_day_and_no_language() -> None:
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
            language=None,
        )
    ]


def test_the_newest_reviews_come_first_and_the_limit_cuts_the_rest() -> None:
    answer = scripted(
        scraped(1, date(2026, 9, 1)), scraped(2, date(2026, 10, 5)), scraped(3, date(2026, 8, 1))
    )
    adapter, _ = sources(answer)
    result = adapter.fetch_reviews(PLACE, None, 2, run_id=RUN)
    assert [r.external_id for r in result] == ["id2", "id1"]


def test_reviews_of_one_day_are_ordered_by_their_exact_time() -> None:
    answer = scripted(scraped(1, date(2026, 10, 5), hour=8), scraped(2, date(2026, 10, 5), hour=20))
    adapter, _ = sources(answer)
    assert [r.external_id for r in adapter.fetch_reviews(PLACE, None, 10, run_id=RUN)] == ["id2", "id1"]


def test_fewer_reviews_than_the_limit_returns_all_of_them() -> None:
    adapter, _ = sources(scripted(scraped(1, date(2026, 9, 1)), scraped(2, date(2026, 9, 2))))
    assert len(adapter.fetch_reviews(PLACE, None, 1000, run_id=RUN)) == 2


def test_an_empty_place_is_an_empty_list_without_error() -> None:
    adapter, log = sources(scripted())
    assert adapter.fetch_reviews(PLACE, None, 10, run_id=RUN) == []
    assert [call.status for call in log.calls] == ["ok"]


def test_an_empty_first_page_of_a_place_that_has_reviews_is_a_source_error() -> None:
    adapter, _ = sources(scripted())
    with pytest.raises(ClientError, match="empty_first_page"):
        adapter.fetch_reviews(PLACE, None, 10, run_id=RUN, known_count=171)


def test_a_known_count_of_zero_accepts_an_empty_answer() -> None:
    adapter, _ = sources(scripted())
    assert adapter.fetch_reviews(PLACE, None, 10, run_id=RUN, known_count=0) == []


def test_since_is_inclusive_and_older_reviews_are_dropped_even_when_the_scraper_returns_them() -> None:
    answer = scripted(
        scraped(1, date(2026, 10, 1)), scraped(2, date(2026, 9, 30)), scraped(3, date(2026, 10, 2))
    )
    adapter, _ = sources(answer)
    result = adapter.fetch_reviews(PLACE, date(2026, 10, 1), 10, run_id=RUN)
    assert [r.external_id for r in result] == ["id3", "id1"]


def test_only_the_place_and_the_limit_go_to_the_scraper_because_it_has_no_date_filter() -> None:
    client = scripted()
    adapter, _ = sources(client)
    adapter.fetch_reviews(PLACE, date(2026, 10, 1), 40, run_id=RUN)
    assert client.calls == [(SCRAPE_GOOGLE_REVIEWS, YasogaNScrape(PLACE.external_id, 40))]


def test_a_review_delivered_twice_is_returned_once() -> None:
    adapter, _ = sources(scripted(scraped(1, date(2026, 9, 1)), scraped(1, date(2026, 9, 1))))
    assert len(adapter.fetch_reviews(PLACE, None, 10, run_id=RUN)) == 1


def test_a_review_without_text_is_kept_with_its_rating() -> None:
    adapter, _ = sources(scripted(scraped(1, date(2026, 9, 1), stars=2, text="")))
    review = adapter.fetch_reviews(PLACE, None, 10, run_id=RUN)[0]
    assert (review.text, review.rating) == ("", 2)


def test_the_date_is_the_utc_day_of_the_timestamp() -> None:
    late = ScrapedReview("x", 4, "t", datetime(2026, 10, 30, 23, 59, tzinfo=UTC))
    adapter, _ = sources(scripted(late))
    assert adapter.fetch_reviews(PLACE, None, 10, run_id=RUN)[0].published_on == date(2026, 10, 30)


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


def test_a_call_costs_nothing_so_a_tiny_run_cap_does_not_stop_a_full_fetch() -> None:
    adapter, log = sources(
        scripted(scraped(1, date(2026, 9, 1)), scraped(2, date(2026, 9, 2))), run_cap="0.01"
    )
    assert len(adapter.fetch_reviews(PLACE, None, 1000, run_id=RUN)) == 2
    assert (log.calls[0].cost, log.calls[0].units, log.calls[0].service) == (Decimal(0), 2, "yasogan")


def test_a_denied_call_and_a_provider_failure_reach_the_caller() -> None:
    denied = Sources(Gateway(GatewayConfig({}, Decimal(5)), {}, FakeClock(START), FakeCallLog()))
    with pytest.raises(GatewayDenied):
        denied.fetch_reviews(PLACE, None, 10, run_id=RUN)

    def fail(_operation: str, _request: object) -> ClientResponse:
        raise ClientError("schema_changed")

    adapter, log = sources(FakeServiceClient(Units("yasogan", "review", 1), fail))
    with pytest.raises(ClientError, match="schema_changed"):
        adapter.fetch_reviews(PLACE, None, 10, run_id=RUN)
    assert [call.status for call in log.calls] == ["failed"]


def test_a_payload_that_is_not_a_tuple_of_reviews_is_a_bad_response() -> None:
    def respond(_operation: str, _request: object) -> ClientResponse:
        return ClientResponse("oops", Units("yasogan", "review", 0))

    adapter, _ = sources(FakeServiceClient(Units("yasogan", "review", 1), respond))
    with pytest.raises(ClientError, match="bad_response"):
        adapter.fetch_reviews(PLACE, None, 10, run_id=RUN)


def test_the_recorded_scraper_output_goes_through_the_whole_chain() -> None:
    transport = FakeTransport(HttpResponse(200, FIXTURE.read_bytes()))
    adapter, log = sources(YasogaNClient("https://yasogan.example", transport))
    result = adapter.fetch_reviews(PLACE, None, 1000, run_id=RUN)
    assert [r.rating for r in result] == [3, 5, 5, 5, 5]  # the star-only Review (`text: null`) is kept
    assert [r.text for r in result][1] == ""
    assert all(r.source is Source.GOOGLE_MAPS and r.place_external_id == PLACE.external_id for r in result)
    assert [r.published_on for r in result] == sorted((r.published_on for r in result), reverse=True)
    assert (log.calls[0].units, log.calls[0].service, log.calls[0].cost) == (5, "yasogan", Decimal(0))
    assert json.loads(transport.requests[0].body)["pages"] == 100
