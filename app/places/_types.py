from collections.abc import Collection, Sequence
from dataclasses import dataclass
from datetime import timedelta
from typing import Protocol

from app.domain import Place


@dataclass(frozen=True)
class Suggestion:
    """One autocomplete line: a Google Maps place the user may pick."""

    place_id: str
    text: str


@dataclass(frozen=True)
class AutocompleteRequest:
    query: str


@dataclass(frozen=True)
class DetailsRequest:
    place_id: str


@dataclass(frozen=True)
class TextSearchRequest:
    query: str
    page: str | None = None


@dataclass(frozen=True)
class GooglePage:
    """One page of a text search, already mapped to Places."""

    places: tuple[Place, ...]
    next_page: str | None


class PlacesUnavailable(Exception):  # noqa: N818 - a result for the caller, not a fault
    """Google Places cannot be used now (outage, rate limit or Budget): tell the user to try later."""

    def __init__(self, reason: str, retry_after: timedelta | None = None) -> None:
        super().__init__(f"places unavailable: {reason}")
        self.reason = reason
        self.retry_after = retry_after


class PlaceNotFound(LookupError):
    """Google Maps has no place with this id."""


class EmptyCompany(ValueError):
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
