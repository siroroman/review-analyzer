from collections.abc import Callable
from datetime import UTC, date
from decimal import Decimal

from app.gateway._types import ClientResponse, ServiceCall, Usage


class FakeCallLog:
    """A CallLog in memory that also answers `total`, as the real repository does."""

    def __init__(self) -> None:
        self.calls: list[ServiceCall] = []

    def record(self, call: ServiceCall) -> None:
        self.calls.append(call)

    def total(self, month_start: date) -> Decimal:
        total = Decimal(0)
        for call in self.calls:
            at = call.at.astimezone(UTC)
            if (at.year, at.month) == (month_start.year, month_start.month):
                total += call.cost
        return total


class FakeServiceClient:
    """A ServiceClient with a scripted estimate and behaviour. Remembers what it was asked."""

    def __init__(self, estimate: Usage, respond: Callable[[str, object], ClientResponse]) -> None:
        self._estimate = estimate
        self._respond = respond
        self.calls: list[tuple[str, object]] = []

    def estimate(self, operation: str, request: object) -> Usage:
        return self._estimate

    def call(self, operation: str, request: object) -> ClientResponse:
        self.calls.append((operation, request))
        return self._respond(operation, request)
