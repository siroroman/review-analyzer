from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

import psycopg
from psycopg import sql

from app.domain import (
    Clock,
    Company,
    DatePrecision,
    Insight,
    InsightType,
    Place,
    Review,
    ReviewTopic,
    RunStatus,
    Sentiment,
    Source,
    Taxonomy,
    Topic,
    TrendPoint,
    advance,
)
from app.gateway import CallStatus, ServiceCall
from app.storage._types import (
    CallFilter,
    RunRecord,
    StoredCompany,
    StoredTaxonomy,
    UnknownPlace,
    UnknownRun,
)

_MIGRATIONS = Path(__file__).parent / "migrations"
_FINAL = (RunStatus.DONE, RunStatus.PARTIAL, RunStatus.FAILED)


class Database:
    """One PostgreSQL connection. Every repository call is one transaction: it all happens or none of it."""

    def __init__(self, conn: "psycopg.Connection[Any]") -> None:
        self._conn = conn

    @contextmanager
    def cursor(self) -> Iterator["psycopg.Cursor[Any]"]:
        with self._conn.transaction(), self._conn.cursor() as cur:
            yield cur

    def close(self) -> None:
        self._conn.close()


def connect(dsn: str) -> Database:
    """Open a connection to `dsn` and bring the schema up to date."""
    conn: psycopg.Connection[Any] = psycopg.connect(dsn, autocommit=True)
    db = Database(conn)
    migrate(db)
    return db


def migrate(db: Database) -> None:
    """Apply the migrations in `migrations/` that this database has not seen, in name order."""
    with db.cursor() as cur:
        cur.execute("SELECT pg_advisory_xact_lock(hashtext('review-analyzer-migrations'))")
        cur.execute("CREATE TABLE IF NOT EXISTS schema_migrations (name text PRIMARY KEY)")
        cur.execute("SELECT name FROM schema_migrations")
        applied = {row[0] for row in cur.fetchall()}
        for path in sorted(_MIGRATIONS.glob("*.sql")):
            if path.name not in applied:
                cur.execute(path.read_text())  # a whole script, no parameters
                cur.execute("INSERT INTO schema_migrations (name) VALUES (%s)", (path.name,))


class PostgresCompanies:
    def __init__(self, db: Database) -> None:
        self._db = db

    def get_or_create(self, company: Company) -> StoredCompany:
        with self._db.cursor() as cur:
            place_ids: list[int] = []
            for place in company.places:
                cur.execute(
                    "INSERT INTO places (source, external_id, name, address) VALUES (%s, %s, %s, %s) "
                    "ON CONFLICT (source, external_id) "
                    "DO UPDATE SET name = excluded.name, address = excluded.address "
                    "RETURNING id",
                    (place.source.value, place.external_id, place.name, place.address),
                )
                place_ids.append(_one(cur)[0])
            cur.execute(
                "INSERT INTO companies (places_key, name, industry) VALUES (%s, %s, %s) "
                "ON CONFLICT (places_key) DO NOTHING RETURNING id",
                (company.places_key, company.name, company.industry),
            )
            created = cur.fetchone()
            if created is not None:
                for position, place_id in enumerate(place_ids):
                    cur.execute(
                        "INSERT INTO company_places (company_id, place_id, position) VALUES (%s, %s, %s)",
                        (created[0], place_id, position),
                    )
        stored = self.get(company.places_key)
        if stored is None:
            raise RuntimeError("a Company just stored is missing")
        return stored

    def get(self, places_key: str) -> StoredCompany | None:
        with self._db.cursor() as cur:
            cur.execute("SELECT id FROM companies WHERE places_key = %s", (places_key,))
            row = cur.fetchone()
            return None if row is None else self._load(cur, row[0])

    def containing(self, source: Source, place_external_id: str) -> list[StoredCompany]:
        with self._db.cursor() as cur:
            cur.execute(
                "SELECT cp.company_id FROM company_places cp JOIN places p ON p.id = cp.place_id "
                "WHERE p.source = %s AND p.external_id = %s ORDER BY cp.company_id",
                (source.value, place_external_id),
            )
            return [self._load(cur, row[0]) for row in cur.fetchall()]

    @staticmethod
    def _load(cur: "psycopg.Cursor[Any]", company_id: int) -> StoredCompany:
        cur.execute("SELECT name, industry FROM companies WHERE id = %s", (company_id,))
        name, industry = _one(cur)
        cur.execute(
            "SELECT p.source, p.external_id, p.name, p.address FROM company_places cp "
            "JOIN places p ON p.id = cp.place_id WHERE cp.company_id = %s ORDER BY cp.position",
            (company_id,),
        )
        places = tuple(
            Place(source=Source(r[0]), external_id=r[1], name=r[2], address=r[3]) for r in cur.fetchall()
        )
        return StoredCompany(company_id, Company(name=name, industry=industry, places=places))


_REVIEW_COLUMNS = (
    "p.external_id, r.source, r.external_id, r.rating, r.text, r.published_on, "
    "r.date_precision, r.language, r.text_hash, r.flagged"
)


def _review(row: tuple[Any, ...]) -> Review:
    return Review(
        place_external_id=row[0],
        source=Source(row[1]),
        external_id=row[2],
        rating=row[3],
        text=row[4],
        published_on=row[5],
        date_precision=DatePrecision(row[6]),
        language=row[7],
        text_hash=row[8],
        flagged=row[9],
    )


class PostgresReviews:
    def __init__(self, db: Database) -> None:
        self._db = db

    def add(self, reviews: Sequence[Review]) -> int:
        with self._db.cursor() as cur:
            place_ids: dict[tuple[Source, str], int] = {}
            for review in reviews:
                key = (review.source, review.place_external_id)
                if key not in place_ids:
                    cur.execute(
                        "SELECT id FROM places WHERE source = %s AND external_id = %s",
                        (key[0].value, key[1]),
                    )
                    row = cur.fetchone()
                    if row is None:
                        raise UnknownPlace(f"{key[0].value}:{key[1]}")
                    place_ids[key] = row[0]
            added = 0
            for review in reviews:
                cur.execute(
                    "INSERT INTO reviews (place_id, source, external_id, rating, text, published_on, "
                    "date_precision, language, text_hash, flagged) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) "
                    "ON CONFLICT (source, external_id) DO NOTHING",
                    (
                        place_ids[(review.source, review.place_external_id)],
                        review.source.value,
                        review.external_id,
                        review.rating,
                        review.text,
                        review.published_on,
                        review.date_precision.value,
                        review.language,
                        review.text_hash,
                        review.flagged,
                    ),
                )
                added += cur.rowcount
            return added

    def list_for_place(self, source: Source, place_external_id: str) -> list[Review]:
        with self._db.cursor() as cur:
            cur.execute(
                f"SELECT {_REVIEW_COLUMNS} FROM reviews r JOIN places p ON p.id = r.place_id "  # noqa: S608
                "WHERE r.source = %s AND p.external_id = %s ORDER BY r.published_on, r.external_id",
                (source.value, place_external_id),
            )
            return [_review(row) for row in cur.fetchall()]

    def save_topics(self, source: Source, taxonomy: StoredTaxonomy, topics: Sequence[ReviewTopic]) -> None:
        with self._db.cursor() as cur:
            for topic in topics:
                cur.execute(
                    "INSERT INTO review_topics "
                    "(review_id, industry, version, topic_key, sentiment, confidence) "
                    "SELECT id, %s, %s, %s, %s, %s FROM reviews WHERE source = %s AND external_id = %s "
                    "ON CONFLICT (review_id, industry, version, topic_key) "
                    "DO UPDATE SET sentiment = excluded.sentiment, confidence = excluded.confidence",
                    (
                        taxonomy.taxonomy.industry,
                        taxonomy.version,
                        topic.topic_key,
                        topic.sentiment.value,
                        topic.confidence,
                        source.value,
                        topic.review_external_id,
                    ),
                )
                if cur.rowcount == 0:
                    raise LookupError(f"no stored Review {source.value}:{topic.review_external_id}")

    def topics_for_place(
        self, source: Source, place_external_id: str, taxonomy: StoredTaxonomy
    ) -> list[ReviewTopic]:
        with self._db.cursor() as cur:
            cur.execute(
                "SELECT r.external_id, t.topic_key, t.sentiment, t.confidence FROM review_topics t "
                "JOIN reviews r ON r.id = t.review_id JOIN places p ON p.id = r.place_id "
                "WHERE r.source = %s AND p.external_id = %s AND t.industry = %s AND t.version = %s "
                "ORDER BY r.published_on, r.external_id, t.topic_key",
                (source.value, place_external_id, taxonomy.taxonomy.industry, taxonomy.version),
            )
            return [
                ReviewTopic(
                    review_external_id=r[0], topic_key=r[1], sentiment=Sentiment(r[2]), confidence=r[3]
                )
                for r in cur.fetchall()
            ]

    def unclassified(self, source: Source, place_external_id: str, taxonomy: StoredTaxonomy) -> list[Review]:
        with self._db.cursor() as cur:
            cur.execute(
                f"SELECT {_REVIEW_COLUMNS} FROM reviews r JOIN places p ON p.id = r.place_id "  # noqa: S608
                "WHERE r.source = %s AND p.external_id = %s AND NOT r.flagged AND NOT EXISTS ("
                "SELECT 1 FROM review_topics t WHERE t.review_id = r.id "
                "AND t.industry = %s AND t.version = %s) "
                "ORDER BY r.published_on, r.external_id",
                (source.value, place_external_id, taxonomy.taxonomy.industry, taxonomy.version),
            )
            return [_review(row) for row in cur.fetchall()]


class PostgresTaxonomies:
    def __init__(self, db: Database) -> None:
        self._db = db

    def save(self, taxonomy: Taxonomy) -> StoredTaxonomy:
        with self._db.cursor() as cur:
            cur.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", (taxonomy.industry,))
            cur.execute(
                "SELECT COALESCE(MAX(version), 0) + 1 FROM taxonomies WHERE industry = %s",
                (taxonomy.industry,),
            )
            version: int = _one(cur)[0]
            cur.execute(
                "INSERT INTO taxonomies (industry, version) VALUES (%s, %s)", (taxonomy.industry, version)
            )
            for position, topic in enumerate(taxonomy.topics):
                cur.execute(
                    "INSERT INTO taxonomy_topics (industry, version, position, key, name, description) "
                    "VALUES (%s, %s, %s, %s, %s, %s)",
                    (taxonomy.industry, version, position, topic.key, topic.name, topic.description),
                )
        return StoredTaxonomy(version, taxonomy)

    def latest(self, industry: str) -> StoredTaxonomy | None:
        with self._db.cursor() as cur:
            cur.execute("SELECT MAX(version) FROM taxonomies WHERE industry = %s", (industry,))
            version = _one(cur)[0]
        return None if version is None else self.get(industry, version)

    def get(self, industry: str, version: int) -> StoredTaxonomy | None:
        with self._db.cursor() as cur:
            cur.execute(
                "SELECT key, name, description FROM taxonomy_topics WHERE industry = %s AND version = %s "
                "ORDER BY position",
                (industry, version),
            )
            topics = tuple(Topic(key=r[0], name=r[1], description=r[2]) for r in cur.fetchall())
        if not topics:
            return None
        return StoredTaxonomy(version, Taxonomy(industry=industry, topics=topics))


def _run(row: tuple[Any, ...]) -> RunRecord:
    return RunRecord(
        id=row[0],
        company_id=row[1],
        status=RunStatus(row[2]),
        budget_cap=row[3],
        created_at=row[4],
        finished_at=row[5],
    )


_RUN_COLUMNS = "id, company_id, status, budget_cap, created_at, finished_at"


class PostgresRuns:
    def __init__(self, db: Database, clock: Clock) -> None:
        self._db = db
        self._clock = clock

    def create(self, company_id: int, budget_cap: Decimal) -> RunRecord:
        with self._db.cursor() as cur:
            try:
                cur.execute(
                    "INSERT INTO runs (company_id, status, budget_cap, created_at) "  # noqa: S608
                    "VALUES (%s, %s, %s, %s) "
                    f"RETURNING {_RUN_COLUMNS}",
                    (company_id, RunStatus.QUEUED.value, budget_cap, self._clock.now()),
                )
            except psycopg.errors.ForeignKeyViolation:
                raise LookupError(f"no stored Company {company_id}") from None
            return _run(_one(cur))

    def get(self, run_id: str) -> RunRecord | None:
        with self._db.cursor() as cur:
            cur.execute(f"SELECT {_RUN_COLUMNS} FROM runs WHERE id = %s", (run_id,))  # noqa: S608
            row = cur.fetchone()
            return None if row is None else _run(row)

    def advance(self, run_id: str, status: RunStatus) -> RunRecord:
        with self._db.cursor() as cur:
            cur.execute("SELECT status FROM runs WHERE id = %s FOR UPDATE", (run_id,))
            row = cur.fetchone()
            if row is None:
                raise UnknownRun(run_id)
            target = advance(RunStatus(row[0]), status)
            cur.execute(
                f"UPDATE runs SET status = %s, finished_at = %s WHERE id = %s RETURNING {_RUN_COLUMNS}",  # noqa: S608
                (target.value, self._clock.now() if target in _FINAL else None, run_id),
            )
            return _run(_one(cur))

    def fresh_for(self, company_id: int, ttl: timedelta) -> RunRecord | None:
        with self._db.cursor() as cur:
            cur.execute(
                f"SELECT {_RUN_COLUMNS} FROM runs WHERE company_id = %s AND status = %s "  # noqa: S608
                "AND finished_at > %s ORDER BY finished_at DESC, id::bigint DESC LIMIT 1",
                (company_id, RunStatus.DONE.value, self._clock.now() - ttl),
            )
            row = cur.fetchone()
            return None if row is None else _run(row)


def _require_run(cur: "psycopg.Cursor[Any]", run_id: str) -> None:
    cur.execute("SELECT 1 FROM runs WHERE id = %s", (run_id,))
    if cur.fetchone() is None:
        raise UnknownRun(run_id)


class PostgresInsights:
    def __init__(self, db: Database) -> None:
        self._db = db

    def save(self, run_id: str, insights: Sequence[Insight]) -> None:
        with self._db.cursor() as cur:
            _require_run(cur, run_id)
            for insight in insights:
                cur.execute(
                    "INSERT INTO insights (run_id, type, period_start, period_end, text, review_ids) "
                    "VALUES (%s, %s, %s, %s, %s, %s)",
                    (
                        run_id,
                        insight.type.value,
                        insight.period_start,
                        insight.period_end,
                        insight.text,
                        list(insight.review_ids),
                    ),
                )

    def for_run(self, run_id: str) -> list[Insight]:
        with self._db.cursor() as cur:
            cur.execute(
                "SELECT type, period_start, period_end, text, review_ids FROM insights "
                "WHERE run_id = %s ORDER BY seq",
                (run_id,),
            )
            return [
                Insight(
                    type=InsightType(r[0]),
                    period_start=r[1],
                    period_end=r[2],
                    text=r[3],
                    review_ids=tuple(r[4]),
                )
                for r in cur.fetchall()
            ]


class PostgresTrends:
    def __init__(self, db: Database) -> None:
        self._db = db

    def save(self, run_id: str, points: Sequence[TrendPoint]) -> None:
        with self._db.cursor() as cur:
            _require_run(cur, run_id)
            for point in points:
                cur.execute(
                    "INSERT INTO trend_points "
                    "(run_id, source, period_start, average_rating, count, sentiment) "
                    "VALUES (%s, %s, %s, %s, %s, %s)",
                    (
                        run_id,
                        point.source.value,
                        point.period_start,
                        point.average_rating,
                        point.count,
                        point.sentiment,
                    ),
                )

    def for_run(self, run_id: str) -> list[TrendPoint]:
        with self._db.cursor() as cur:
            cur.execute(
                "SELECT source, period_start, average_rating, count, sentiment FROM trend_points "
                "WHERE run_id = %s ORDER BY seq",
                (run_id,),
            )
            return [
                TrendPoint(
                    source=Source(r[0]), period_start=r[1], average_rating=r[2], count=r[3], sentiment=r[4]
                )
                for r in cur.fetchall()
            ]


_CALL_COLUMNS = "service, operation, run_id, status, cost, unit, units, latency, error_kind, at"


def _call(row: tuple[Any, ...]) -> ServiceCall:
    status: CallStatus = row[3]
    return ServiceCall(
        service=row[0],
        operation=row[1],
        run_id=row[2],
        status=status,
        cost=row[4],
        unit=row[5],
        units=row[6],
        latency=row[7],
        error_kind=row[8],
        at=row[9],
    )


def _where(where: CallFilter) -> tuple[sql.Composable, list[object]]:
    clauses: list[sql.Composable] = []
    params: list[object] = []
    for column, op, value in (
        ("service", "=", where.service),
        ("operation", "=", where.operation),
        ("run_id", "=", where.run_id),
        ("status", "=", where.status),
        ("at", ">=", where.since),
        ("at", "<", where.until),
    ):
        if value is not None:
            clauses.append(sql.SQL("{} {} %s").format(sql.Identifier(column), sql.SQL(op)))
            params.append(value)
    return sql.SQL(" AND ").join(clauses) if clauses else sql.SQL("TRUE"), params


class PostgresServiceCalls:
    def __init__(self, db: Database) -> None:
        self._db = db

    def record(self, call: ServiceCall) -> None:
        with self._db.cursor() as cur:
            cur.execute(
                f"INSERT INTO service_calls ({_CALL_COLUMNS}) "  # noqa: S608
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                (
                    call.service,
                    call.operation,
                    call.run_id,
                    call.status,
                    call.cost,
                    call.unit,
                    call.units,
                    call.latency,
                    call.error_kind,
                    call.at,
                ),
            )

    def total(self, month_start: date) -> Decimal:
        first = date(month_start.year, month_start.month, 1)
        following = date(first.year + (first.month == 12), first.month % 12 + 1, 1)
        with self._db.cursor() as cur:
            cur.execute(
                "SELECT COALESCE(SUM(cost), 0) FROM service_calls "
                "WHERE (at AT TIME ZONE 'UTC') >= %s AND (at AT TIME ZONE 'UTC') < %s",
                (first, following),
            )
            return Decimal(_one(cur)[0])

    def query(self, where: CallFilter) -> list[ServiceCall]:
        condition, params = _where(where)
        query = sql.SQL("SELECT {} FROM service_calls WHERE {} ORDER BY at, seq").format(
            sql.SQL(_CALL_COLUMNS), condition
        )
        with self._db.cursor() as cur:
            cur.execute(query, params)
            return [_call(row) for row in cur.fetchall()]

    def cost_by_service(self, where: CallFilter) -> dict[str, Decimal]:
        return self._sums("service", where)

    def cost_by_day(self, where: CallFilter) -> dict[date, Decimal]:
        return self._sums("(at AT TIME ZONE 'UTC')::date", where)

    def cost_by_run(self, where: CallFilter) -> dict[str, Decimal]:
        return self._sums("run_id", where)

    def _sums[K](self, group: str, where: CallFilter) -> dict[K, Decimal]:
        condition, params = _where(where)
        query = sql.SQL(
            "SELECT {group}, SUM(cost) FROM service_calls WHERE {cond} GROUP BY 1 ORDER BY 1"
        ).format(group=sql.SQL(group), cond=condition)
        with self._db.cursor() as cur:
            cur.execute(query, params)
            return {row[0]: Decimal(row[1]) for row in cur.fetchall()}


def _one(cur: "psycopg.Cursor[Any]") -> tuple[Any, ...]:
    row = cur.fetchone()
    if row is None:
        raise RuntimeError("the statement returned no row")
    return tuple(row)
