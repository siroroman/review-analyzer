from collections.abc import Collection, Sequence
from datetime import timedelta
from typing import Protocol

from app.domain import Place


class PlacesUnavailable(Exception):  # noqa: N818 - a result for the caller, not a fault
    """Google Places cannot be used now (outage, rate limit or Budget): tell the user to try later."""

    def __init__(self, reason: str, retry_after: timedelta | None = None) -> None:
        super().__init__(f"places unavailable: {reason}")
        self.reason = reason
        self.retry_after = retry_after


class PlaceNotFound(LookupError):
    """Google Maps has no place with this id."""


class InvalidCompany(ValueError):
    """The input of `confirm` cannot make a Company; raised before any paid call."""


class EmptyCompany(InvalidCompany):
    """A Company needs at least one Place."""


class OtherSourceUnavailable(Exception):  # noqa: N818 - a result for the caller, not a fault
    """The other Source could not be searched now."""


class OtherSourceSearch(Protocol):
    """Port: finds candidate Places of one other Source (Firmy.cz) by name and address."""

    def search(self, name: str, address: str) -> Collection[Place]:
        """Raises `OtherSourceUnavailable` when the Source cannot be searched."""
        ...


class FakeOtherSource:
    """An `OtherSourceSearch` with scripted candidates. Remembers what it was asked."""

    def __init__(self, candidates: Sequence[Place] = (), *, fail: bool = False) -> None:
        self._candidates = tuple(candidates)
        self._fail = fail
        self.asked: list[tuple[str, str]] = []

    def search(self, name: str, address: str) -> Collection[Place]:
        self.asked.append((name, address))
        if self._fail:
            raise OtherSourceUnavailable
        return self._candidates
