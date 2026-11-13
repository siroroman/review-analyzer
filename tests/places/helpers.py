from collections.abc import Callable, Sequence
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from app.budget import Units
from app.domain import FakeClock, Place, Source
from app.gateway import (
    GOOGLE_PLACES,
    AutocompleteRequest,
    ClientError,
    ClientResponse,
    DetailsRequest,
    FakeCallLog,
    FakeServiceClient,
    Gateway,
    GatewayConfig,
    GooglePage,
    ServicePolicy,
    Suggestion,
    TextSearchRequest,
)
from app.places import FakeOtherSource, Places

START = datetime(2026, 11, 13, 9, 0, tzinfo=UTC)
RUN = "run-1"
OPERATIONS = frozenset({"autocomplete", "details", "text_search"})


def google(external_id: str, name: str = "Globus Hypermarket", address: str = "Praha") -> Place:
    return Place(source=Source.GOOGLE_MAPS, external_id=external_id, name=name, address=address)


def firmy(external_id: str, name: str, address: str) -> Place:
    return Place(source=Source.FIRMY_CZ, external_id=external_id, name=name, address=address)


class Google:
    """A scripted Google Places: what it knows, and what it fails with."""

    def __init__(self) -> None:
        self.suggestions: dict[str, tuple[Suggestion, ...]] = {}
        self.known: dict[str, Place] = {}
        self.pages: list[GooglePage] = []
        self.error: Exception | None = None
        self.client = FakeServiceClient(Units(GOOGLE_PLACES, "details_request", 1), self._respond)

    def _respond(self, operation: str, request: object) -> ClientResponse:
        if self.error is not None:
            raise self.error
        usage = Units(GOOGLE_PLACES, "details_request", 1)
        if operation == "autocomplete" and isinstance(request, AutocompleteRequest):
            return ClientResponse(self.suggestions.get(request.query, ()), usage)
        if operation == "details" and isinstance(request, DetailsRequest):
            if request.place_id not in self.known:
                raise ClientError("not_found")
            return ClientResponse(self.known[request.place_id], usage)
        if operation == "text_search" and isinstance(request, TextSearchRequest):
            return ClientResponse(self.pages.pop(0) if self.pages else GooglePage((), None), usage)
        raise AssertionError(f"unexpected call {operation}")

    def asked(self, operation: str) -> list[object]:
        return [request for name, request in self.client.calls if name == operation]


class Setup:
    """Places over the real Gateway with a fake Google, a fake other Source, a fake clock and Call log."""

    def __init__(
        self,
        candidates: Sequence[Place] = (),
        *,
        run_cap: str = "5",
        max_calls: int = 100,
        other_fails: bool = False,
    ) -> None:
        self.clock = FakeClock(START)
        self.log = FakeCallLog()
        self.google = Google()
        self.other = FakeOtherSource(candidates, fail=other_fails)
        policy = ServicePolicy(OPERATIONS, max_calls, timedelta(seconds=60), 4)
        gateway = Gateway(
            GatewayConfig({GOOGLE_PLACES: policy}, Decimal(run_cap), Decimal(30)),
            {GOOGLE_PLACES: self.google.client},
            self.clock,
            self.log,
        )
        self.places = Places(gateway, self.other)


def pages(*batches: Sequence[Place]) -> list[GooglePage]:
    """Pages of a text search; every page but the last has a token for the next one."""
    return [
        GooglePage(tuple(batch), f"next-{index}" if index < len(batches) - 1 else None)
        for index, batch in enumerate(batches)
    ]


Respond = Callable[[str, object], ClientResponse]
