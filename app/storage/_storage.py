from collections.abc import Callable
from dataclasses import dataclass

from app.domain import Clock, Insight, TrendPoint
from app.storage._memory import (
    MemoryCompanies,
    MemoryResults,
    MemoryReviews,
    MemoryRuns,
    MemoryServiceCalls,
    MemoryTaxonomies,
)
from app.storage._postgres import (
    PostgresCompanies,
    PostgresInsights,
    PostgresReviews,
    PostgresRuns,
    PostgresServiceCalls,
    PostgresTaxonomies,
    PostgresTrends,
    connect,
)
from app.storage._types import (
    CompanyRepo,
    InsightRepo,
    ReviewRepo,
    RunRepo,
    ServiceCallRepo,
    TaxonomyRepo,
    TrendRepo,
)


@dataclass(frozen=True)
class Storage:
    """Every repository over one store. `close` releases the connection of a database, if any."""

    companies: CompanyRepo
    reviews: ReviewRepo
    taxonomies: TaxonomyRepo
    runs: RunRepo
    insights: InsightRepo
    trends: TrendRepo
    calls: ServiceCallRepo
    close: Callable[[], None]


def in_memory_storage(clock: Clock) -> Storage:
    """A store that lives in the process; the fake of the PostgreSQL one, held to the same contract tests."""
    companies = MemoryCompanies()
    runs = MemoryRuns(clock, companies)
    return Storage(
        companies=companies,
        reviews=MemoryReviews(companies.places),
        taxonomies=MemoryTaxonomies(),
        runs=runs,
        insights=MemoryResults[Insight](runs),
        trends=MemoryResults[TrendPoint](runs),
        calls=MemoryServiceCalls(),
        close=lambda: None,
    )


def postgres_storage(dsn: str, clock: Clock) -> Storage:
    """Connect to the PostgreSQL database `dsn`, bring its schema up to date and return the repositories."""
    db = connect(dsn)
    return Storage(
        companies=PostgresCompanies(db),
        reviews=PostgresReviews(db),
        taxonomies=PostgresTaxonomies(db),
        runs=PostgresRuns(db, clock),
        insights=PostgresInsights(db),
        trends=PostgresTrends(db),
        calls=PostgresServiceCalls(db),
        close=db.close,
    )
