from collections.abc import Iterator

import psycopg
import pytest
from testcontainers.community.postgres import PostgresContainer

from app.domain import FakeClock
from app.storage import Storage, in_memory_storage, postgres_storage
from tests.storage.helpers import START

# Data tables only: `taxonomies` rows are immutable by trigger, but TRUNCATE is not a row change.
_TABLES = (
    "service_calls, trend_points, insights, runs, review_topics, taxonomy_topics, taxonomies, "
    "reviews, company_places, places, companies"
)


@pytest.fixture(scope="session")
def postgres_dsn() -> Iterator[str]:
    """One real PostgreSQL for the whole session, started by testcontainers."""
    with PostgresContainer("postgres:16-alpine", driver=None) as container:
        yield container.get_connection_url()


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock(START)


@pytest.fixture(params=["memory", "postgres"])
def storage(request: pytest.FixtureRequest, clock: FakeClock) -> Iterator[Storage]:
    """Every contract test runs on every implementation of the repositories."""
    if request.param == "memory":
        yield in_memory_storage(clock)
        return
    dsn: str = request.getfixturevalue("postgres_dsn")
    store = postgres_storage(dsn, clock)
    try:
        yield store
    finally:
        with psycopg.connect(dsn, autocommit=True) as conn:
            conn.execute(f"TRUNCATE {_TABLES} RESTART IDENTITY")
        store.close()
