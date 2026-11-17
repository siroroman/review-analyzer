from datetime import date, timedelta
from decimal import Decimal

import pytest

from app.domain import Place, PlaceDetails, PlaceResult, RunStatus, Source
from app.gateway import BudgetExceeded, ClientError, GatewayDenied
from tests.pipeline.helpers import INJECTION, PLACE, World, month_of_reviews, scraped

FIRST = PlaceDetails(rating=4.3, review_count=26348)
SECOND = PlaceDetails(rating=4.4, review_count=26400)
PAST_THE_CACHE = timedelta(days=30)  # a Company's fresh Run is reused for 24 hours


class ScriptedDetails:
    """A details source that answers or fails in the order given. Remembers who it was asked about."""

    def __init__(self, *steps: PlaceDetails | Exception) -> None:
        self._steps = list(steps)
        self.asked: list[tuple[Place, str]] = []

    def fetch_place_details(self, place: Place, *, run_id: str) -> PlaceDetails:
        self.asked.append((place, run_id))
        step = self._steps.pop(0)
        if isinstance(step, Exception):
            raise step
        return step


def stored(world: World) -> PlaceDetails | None:
    return world.storage.companies.place_details(Source.GOOGLE_MAPS, PLACE.external_id)


def test_a_run_stores_the_details_of_its_place() -> None:
    details = ScriptedDetails(FIRST)
    world = World(place_details=details)

    result = world.run()

    assert result.status is RunStatus.DONE
    assert stored(world) == FIRST
    assert details.asked == [(PLACE, result.run_id)]


def test_every_run_refreshes_the_details() -> None:
    world = World(place_details=ScriptedDetails(FIRST, SECOND))
    world.run()
    world.clock.advance(PAST_THE_CACHE)

    world.run()

    assert stored(world) == SECOND


@pytest.mark.parametrize(
    "failure",
    [
        ClientError("not_found"),
        ClientError("ambiguous"),
        ClientError("schema_changed"),
        GatewayDenied("gosom", "get_place_details", "service_not_allowed"),
        BudgetExceeded("run", Decimal(5), Decimal(6)),
    ],
)
def test_a_failed_details_call_gives_a_run_without_details_not_a_failed_run(failure: Exception) -> None:
    world = World(place_details=ScriptedDetails(failure))

    result = world.run()

    assert result.status is RunStatus.DONE
    assert stored(world) is None


def test_a_failed_refresh_keeps_the_details_of_the_earlier_run() -> None:
    world = World(
        place_details=ScriptedDetails(FIRST, ClientError("server_error"), ClientError("server_error"))
    )
    world.run()
    world.clock.advance(PAST_THE_CACHE)

    result = world.run()

    assert result.status is RunStatus.DONE
    assert stored(world) == FIRST


def test_a_transient_failure_is_retried_like_any_provider_call() -> None:
    world = World(place_details=ScriptedDetails(ClientError("timeout"), FIRST))

    world.run()

    assert stored(world) == FIRST


def test_a_run_without_a_details_source_stores_none() -> None:
    world = World()

    assert world.run().status is RunStatus.DONE
    assert stored(world) is None


def _place_result(world: World, run_id: str) -> PlaceResult:
    (only,) = world.pipeline.report(run_id).places
    return only


def test_a_report_gives_the_places_totals_and_how_many_reviews_were_analyzed() -> None:
    details = PlaceDetails(
        rating=4.3,
        review_count=26348,
        reviews_per_rating={5: 20000, 4: 4000, 3: 1000, 2: 500, 1: 848},
        category="Cafe",
        address="Praha 1",
        phone="+420 123 456 789",
        website="https://example.cz",
        maps_url="https://maps.google.com/?cid=1",
        thumbnail_url="https://example.cz/t.jpg",
    )
    world = World(place_details=ScriptedDetails(details))

    result = _place_result(world, world.run().run_id)

    assert (result.source, result.place_external_id) == (Source.GOOGLE_MAPS, PLACE.external_id)
    assert result.details == details
    assert result.analyzed_count == 40
    assert result.analyzed_is_limited is True  # 26348 on Google Maps, only the fetched ones analyzed


def test_a_place_whose_reviews_were_all_analyzed_is_not_limited() -> None:
    world = World(place_details=ScriptedDetails(PlaceDetails(rating=4.3, review_count=40)))

    result = _place_result(world, world.run().run_id)

    assert (result.analyzed_count, result.analyzed_is_limited) == (40, False)


def test_a_failed_details_call_leaves_the_totals_empty_and_the_count_from_the_fetched_reviews() -> None:
    world = World(place_details=ScriptedDetails(ClientError("not_found")))

    result = _place_result(world, world.run().run_id)

    assert result.details is None
    assert (result.analyzed_count, result.analyzed_is_limited) == (40, False)


def test_flagged_reviews_are_not_analyzed_and_reviews_without_text_are_counted() -> None:
    fetched = [
        scraped(0, date(2026, 10, 1)),
        scraped(1, date(2026, 10, 2), text=INJECTION),
        scraped(2, date(2026, 10, 3), text=""),
    ]
    world = World(
        scraped_reviews=fetched, place_details=ScriptedDetails(PlaceDetails(rating=4, review_count=3))
    )

    result = _place_result(world, world.run().run_id)

    assert result.analyzed_count == 2
    assert result.analyzed_is_limited is False  # 3 Reviews are far below the limit; Flagged is not a limit


def test_a_place_with_more_reviews_than_the_limit_is_limited_and_one_within_it_is_not() -> None:
    big = World(
        scraped_reviews=month_of_reviews(1000),
        place_details=ScriptedDetails(PlaceDetails(rating=4.3, review_count=26348)),
    )
    whole = World(
        scraped_reviews=month_of_reviews(800),
        place_details=ScriptedDetails(PlaceDetails(rating=4.3, review_count=800)),
    )

    limited = _place_result(big, big.run().run_id)
    unlimited = _place_result(whole, whole.run().run_id)

    assert (limited.analyzed_count, limited.analyzed_is_limited) == (1000, True)
    assert (unlimited.analyzed_count, unlimited.analyzed_is_limited) == (800, False)


def test_a_flagged_review_of_a_place_within_the_limit_does_not_make_it_limited() -> None:
    fetched = [scraped(i, date(2026, 10, 1 + i % 28)) for i in range(799)]
    fetched.append(scraped(799, date(2026, 10, 1), text=INJECTION))
    world = World(
        scraped_reviews=fetched,
        place_details=ScriptedDetails(PlaceDetails(rating=4.3, review_count=800)),
    )

    result = _place_result(world, world.run().run_id)

    assert (result.analyzed_count, result.analyzed_is_limited) == (799, False)
