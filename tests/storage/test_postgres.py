"""What only PostgreSQL has: the schema, the triggers and the migrations."""

import psycopg
import pytest

from app.domain import FakeClock, Taxonomy, Topic
from app.storage import postgres_storage


def _columns(dsn: str, table: str) -> set[str]:
    with psycopg.connect(dsn) as conn:
        rows = conn.execute(
            "SELECT column_name FROM information_schema.columns WHERE table_name = %s", (table,)
        ).fetchall()
    return {row[0] for row in rows}


def test_reviews_have_no_column_for_reviewer_data(postgres_dsn: str, clock: FakeClock) -> None:
    postgres_storage(postgres_dsn, clock).close()
    assert _columns(postgres_dsn, "reviews") == {
        "id",
        "place_id",
        "source",
        "external_id",
        "rating",
        "text",
        "published_on",
        "date_precision",
        "language",
        "text_hash",
        "flagged",
    }


def test_the_call_log_has_no_column_for_a_request_or_response_body(
    postgres_dsn: str, clock: FakeClock
) -> None:
    postgres_storage(postgres_dsn, clock).close()
    assert _columns(postgres_dsn, "service_calls") == {
        "seq",
        "service",
        "operation",
        "run_id",
        "status",
        "cost",
        "unit",
        "units",
        "latency",
        "error_kind",
        "at",
    }


def test_a_stored_taxonomy_version_cannot_be_changed_or_deleted(postgres_dsn: str, clock: FakeClock) -> None:
    store = postgres_storage(postgres_dsn, clock)
    store.taxonomies.save(Taxonomy(industry="immutable", topics=(Topic(key="a", name="A", description=""),)))
    with psycopg.connect(postgres_dsn, autocommit=True) as conn:
        for statement in (
            "UPDATE taxonomy_topics SET name = 'changed' WHERE industry = 'immutable'",
            "DELETE FROM taxonomy_topics WHERE industry = 'immutable'",
            "UPDATE taxonomies SET version = 9 WHERE industry = 'immutable'",
            "DELETE FROM taxonomies WHERE industry = 'immutable'",
        ):
            with pytest.raises(psycopg.errors.IntegrityConstraintViolation):
                conn.execute(statement)
    saved = store.taxonomies.get("immutable", 1)
    assert saved is not None
    assert saved.taxonomy.topics[0].name == "A"
    store.close()


def test_migrations_run_once_and_connecting_again_changes_nothing(
    postgres_dsn: str, clock: FakeClock
) -> None:
    postgres_storage(postgres_dsn, clock).close()
    postgres_storage(postgres_dsn, clock).close()
    with psycopg.connect(postgres_dsn) as conn:
        names = [row[0] for row in conn.execute("SELECT name FROM schema_migrations").fetchall()]
    assert names == ["0001_init.sql"]
