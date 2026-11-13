from collections import defaultdict
from collections.abc import Callable, Sequence
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from app.domain import (
    Clock,
    Company,
    Place,
    Review,
    ReviewTopic,
    RunStatus,
    Source,
    Taxonomy,
    advance,
)
from app.gateway import ServiceCall
from app.storage._types import (
    CallFilter,
    RunRecord,
    StoredCompany,
    StoredTaxonomy,
    UnknownPlace,
    UnknownRun,
)

_FINAL = (RunStatus.DONE, RunStatus.PARTIAL, RunStatus.FAILED)


class MemoryCompanies:
    def __init__(self) -> None:
        # key -> (id, name, industry, Place keys in the order first given)
        self._companies: dict[str, tuple[int, str, str, tuple[tuple[Source, str], ...]]] = {}
        self.places: dict[tuple[Source, str], Place] = {}

    def get_or_create(self, company: Company) -> StoredCompany:
        for place in company.places:
            self.places[(place.source, place.external_id)] = place
        if company.places_key not in self._companies:
            keys = tuple((p.source, p.external_id) for p in company.places)
            self._companies[company.places_key] = (
                len(self._companies) + 1,
                company.name,
                company.industry,
                keys,
            )
        return self._build(company.places_key)

    def get(self, places_key: str) -> StoredCompany | None:
        return self._build(places_key) if places_key in self._companies else None

    def containing(self, source: Source, place_external_id: str) -> list[StoredCompany]:
        return [
            self._build(key)
            for key, (_, _, _, places) in self._companies.items()
            if (source, place_external_id) in places
        ]

    def ids(self) -> set[int]:
        return {entry[0] for entry in self._companies.values()}

    def _build(self, key: str) -> StoredCompany:
        company_id, name, industry, places = self._companies[key]
        return StoredCompany(
            company_id, Company(name=name, industry=industry, places=tuple(self.places[k] for k in places))
        )


class MemoryReviews:
    def __init__(self, places: dict[tuple[Source, str], Place]) -> None:
        self._places = places
        self._reviews: dict[tuple[Source, str], Review] = {}
        self._topics: dict[tuple[Source, str, str, int, str], ReviewTopic] = {}

    def add(self, reviews: Sequence[Review]) -> int:
        for review in reviews:
            if (review.source, review.place_external_id) not in self._places:
                raise UnknownPlace(f"{review.source.value}:{review.place_external_id}")
        added = 0
        for review in reviews:
            if (review.source, review.external_id) not in self._reviews:
                self._reviews[(review.source, review.external_id)] = review
                added += 1
        return added

    def list_for_place(self, source: Source, place_external_id: str) -> list[Review]:
        found = [
            r
            for r in self._reviews.values()
            if (r.source, r.place_external_id) == (source, place_external_id)
        ]
        return sorted(found, key=lambda r: (r.published_on, r.external_id))

    def save_topics(self, source: Source, taxonomy: StoredTaxonomy, topics: Sequence[ReviewTopic]) -> None:
        for topic in topics:
            if (source, topic.review_external_id) not in self._reviews:
                raise LookupError(f"no stored Review {source.value}:{topic.review_external_id}")
        for topic in topics:
            key = (
                source,
                topic.review_external_id,
                taxonomy.taxonomy.industry,
                taxonomy.version,
                topic.topic_key,
            )
            self._topics[key] = topic

    def topics_for_place(
        self, source: Source, place_external_id: str, taxonomy: StoredTaxonomy
    ) -> list[ReviewTopic]:
        ids = {r.external_id: i for i, r in enumerate(self.list_for_place(source, place_external_id))}
        found = [
            topic
            for (src, review_id, industry, version, _), topic in self._topics.items()
            if src == source
            and review_id in ids
            and (industry, version) == (taxonomy.taxonomy.industry, taxonomy.version)
        ]
        return sorted(found, key=lambda t: (ids[t.review_external_id], t.topic_key))

    def unclassified(self, source: Source, place_external_id: str, taxonomy: StoredTaxonomy) -> list[Review]:
        done = {t.review_external_id for t in self.topics_for_place(source, place_external_id, taxonomy)}
        return [
            r
            for r in self.list_for_place(source, place_external_id)
            if not r.flagged and r.external_id not in done
        ]


class MemoryTaxonomies:
    def __init__(self) -> None:
        self._versions: dict[str, list[StoredTaxonomy]] = defaultdict(list)

    def save(self, taxonomy: Taxonomy) -> StoredTaxonomy:
        versions = self._versions[taxonomy.industry]
        stored = StoredTaxonomy(len(versions) + 1, taxonomy)
        versions.append(stored)
        return stored

    def latest(self, industry: str) -> StoredTaxonomy | None:
        versions = self._versions.get(industry)
        return versions[-1] if versions else None

    def get(self, industry: str, version: int) -> StoredTaxonomy | None:
        versions = self._versions.get(industry, [])
        return versions[version - 1] if 1 <= version <= len(versions) else None


class MemoryRuns:
    def __init__(self, clock: Clock, companies: MemoryCompanies) -> None:
        self._clock = clock
        self._companies = companies
        self._runs: dict[str, RunRecord] = {}

    def create(self, company_id: int, budget_cap: Decimal) -> RunRecord:
        if company_id not in self._companies.ids():
            raise LookupError(f"no stored Company {company_id}")
        run = RunRecord(
            str(len(self._runs) + 1), company_id, RunStatus.QUEUED, budget_cap, self._clock.now(), None
        )
        self._runs[run.id] = run
        return run

    def get(self, run_id: str) -> RunRecord | None:
        return self._runs.get(run_id)

    def has(self, run_id: str) -> bool:
        return run_id in self._runs

    def advance(self, run_id: str, status: RunStatus) -> RunRecord:
        run = self._runs.get(run_id)
        if run is None:
            raise UnknownRun(run_id)
        target = advance(run.status, status)
        finished_at = self._clock.now() if target in _FINAL else None
        moved = RunRecord(run.id, run.company_id, target, run.budget_cap, run.created_at, finished_at)
        self._runs[run_id] = moved
        return moved

    def fresh_for(self, company_id: int, ttl: timedelta) -> RunRecord | None:
        now = self._clock.now()
        fresh = [
            run
            for run in self._runs.values()
            if run.company_id == company_id
            and run.status is RunStatus.DONE
            and run.finished_at is not None
            and now - run.finished_at < ttl
        ]
        return max(fresh, key=lambda run: (run.finished_at, int(run.id)), default=None)


class MemoryResults[T]:
    """Insights or TrendPoints of Runs: append-only lists per Run."""

    def __init__(self, runs: MemoryRuns) -> None:
        self._runs = runs
        self._by_run: dict[str, list[T]] = defaultdict(list)

    def save(self, run_id: str, items: Sequence[T]) -> None:
        if not self._runs.has(run_id):
            raise UnknownRun(run_id)
        self._by_run[run_id].extend(items)

    def for_run(self, run_id: str) -> list[T]:
        return list(self._by_run.get(run_id, []))


def _utc_day(at: datetime) -> date:
    return at.astimezone(UTC).date()


class MemoryServiceCalls:
    def __init__(self) -> None:
        self._calls: list[ServiceCall] = []

    def record(self, call: ServiceCall) -> None:
        self._calls.append(call)

    def total(self, month_start: date) -> Decimal:
        month = (month_start.year, month_start.month)
        return sum(
            (c.cost for c in self._calls if (_utc_day(c.at).year, _utc_day(c.at).month) == month), Decimal(0)
        )

    def query(self, where: CallFilter) -> list[ServiceCall]:
        matching = [c for c in self._calls if _matches(c, where)]
        return sorted(matching, key=lambda c: c.at)  # stable: ties keep the order recorded

    def cost_by_service(self, where: CallFilter) -> dict[str, Decimal]:
        return self._sum(where, lambda c: c.service)

    def cost_by_day(self, where: CallFilter) -> dict[date, Decimal]:
        return self._sum(where, lambda c: _utc_day(c.at))

    def cost_by_run(self, where: CallFilter) -> dict[str, Decimal]:
        return self._sum(where, lambda c: c.run_id)

    def _sum[K](self, where: CallFilter, key: Callable[[ServiceCall], K]) -> dict[K, Decimal]:
        sums: dict[K, Decimal] = {}
        for call in self.query(where):
            sums[key(call)] = sums.get(key(call), Decimal(0)) + call.cost
        return sums


def _matches(call: ServiceCall, where: CallFilter) -> bool:
    return (
        (where.service is None or call.service == where.service)
        and (where.operation is None or call.operation == where.operation)
        and (where.run_id is None or call.run_id == where.run_id)
        and (where.status is None or call.status == where.status)
        and (where.since is None or call.at >= where.since)
        and (where.until is None or call.at < where.until)
    )
