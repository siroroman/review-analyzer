from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Protocol

from app.domain import (
    Company,
    Insight,
    Review,
    ReviewTopic,
    RunStatus,
    Source,
    Taxonomy,
    TrendPoint,
)
from app.gateway import CallStatus, ServiceCall


@dataclass(frozen=True)
class StoredCompany:
    """A Company with the id storage gave it."""

    id: int
    company: Company


@dataclass(frozen=True)
class StoredTaxonomy:
    """One immutable version of the Taxonomy of an industry; versions count from 1."""

    version: int
    taxonomy: Taxonomy


@dataclass(frozen=True)
class RunRecord:
    """A Run as stored; `finished_at` is set when it reaches a final status."""

    id: str
    company_id: int
    status: RunStatus
    budget_cap: Decimal
    created_at: datetime
    finished_at: datetime | None


@dataclass(frozen=True)
class CallFilter:
    """Which Service calls to read. Every field left `None` matches anything.

    The date range is half-open: `since <= call.at < until`.
    """

    service: str | None = None
    operation: str | None = None
    run_id: str | None = None
    status: CallStatus | None = None
    since: datetime | None = None
    until: datetime | None = None


class UnknownPlace(LookupError):
    """A Review names a Place that no stored Company contains."""


class UnknownRun(LookupError):
    """No Run has this id."""


class CompanyRepo(Protocol):
    def get_or_create(self, company: Company) -> StoredCompany:
        """Return the stored Company with the same `places_key`, or store this one.

        The same set of Places is the same Company whatever its order or name; the first name wins.
        A Place seen again takes the newest name and address. One Place may belong to several Companies.
        """
        ...

    def get(self, places_key: str) -> StoredCompany | None: ...

    def containing(self, source: Source, place_external_id: str) -> list[StoredCompany]:
        """Every Company that lists this Place, oldest first."""
        ...


class ReviewRepo(Protocol):
    def add(self, reviews: Sequence[Review]) -> int:
        """Store the Reviews, return how many were new. (source, external_id) is unique; a repeat is skipped.

        Raises `UnknownPlace` (and stores none) when a Review names a Place no Company contains.
        """
        ...

    def list_for_place(self, source: Source, place_external_id: str) -> list[Review]:
        """The Reviews of one Place, oldest first (ties by external ID)."""
        ...

    def save_topics(self, source: Source, taxonomy: StoredTaxonomy, topics: Sequence[ReviewTopic]) -> None:
        """Store ReviewTopics for one Taxonomy version; a repeated Review and Topic replaces."""
        ...

    def topics_for_place(
        self, source: Source, place_external_id: str, taxonomy: StoredTaxonomy
    ) -> list[ReviewTopic]: ...

    def unclassified(self, source: Source, place_external_id: str, taxonomy: StoredTaxonomy) -> list[Review]:
        """Reviews of the Place without any ReviewTopic for this Taxonomy version (Flagged ones excluded)."""
        ...


class TaxonomyRepo(Protocol):
    def save(self, taxonomy: Taxonomy) -> StoredTaxonomy:
        """Store a new version of the industry's Taxonomy. A stored version never changes."""
        ...

    def latest(self, industry: str) -> StoredTaxonomy | None: ...

    def get(self, industry: str, version: int) -> StoredTaxonomy | None: ...


class RunRepo(Protocol):
    def create(self, company_id: int, budget_cap: Decimal) -> RunRecord:
        """Start a `queued` Run for a stored Company."""
        ...

    def get(self, run_id: str) -> RunRecord | None: ...

    def advance(self, run_id: str, status: RunStatus) -> RunRecord:
        """Move the Run forward by the rules of `domain.advance`. Raises `UnknownRun`, `InvalidTransition`."""
        ...

    def fresh_for(self, company_id: int, ttl: timedelta) -> RunRecord | None:
        """The newest `done` Run of the Company that finished less than `ttl` ago by the Clock: the cache."""
        ...


class InsightRepo(Protocol):
    def save(self, run_id: str, insights: Sequence[Insight]) -> None:
        """Append Insights to a Run. Raises `UnknownRun`."""
        ...

    def for_run(self, run_id: str) -> list[Insight]:
        """In the order they were saved."""
        ...


class TrendRepo(Protocol):
    def save(self, run_id: str, points: Sequence[TrendPoint]) -> None:
        """Append TrendPoints to a Run. Raises `UnknownRun`."""
        ...

    def for_run(self, run_id: str) -> list[TrendPoint]:
        """In the order they were saved."""
        ...


class ServiceCallRepo(Protocol):
    """The Call log. Also the `CallLog` port of `gateway`: `record` and `total`."""

    def record(self, call: ServiceCall) -> None: ...

    def total(self, month_start: date) -> Decimal:
        """Cost of every Service call in the calendar month (UTC) of `month_start`."""
        ...

    def query(self, where: CallFilter) -> list[ServiceCall]:
        """Matching calls, oldest first (ties in the order recorded)."""
        ...

    def cost_by_service(self, where: CallFilter) -> dict[str, Decimal]: ...

    def cost_by_day(self, where: CallFilter) -> dict[date, Decimal]:
        """Days are UTC days."""
        ...

    def cost_by_run(self, where: CallFilter) -> dict[str, Decimal]: ...
