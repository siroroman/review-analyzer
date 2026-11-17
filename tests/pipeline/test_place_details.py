from datetime import timedelta
from decimal import Decimal

import pytest

from app.domain import Place, PlaceDetails, RunStatus, Source
from app.gateway import BudgetExceeded, ClientError, GatewayDenied
from tests.pipeline.helpers import PLACE, World

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
