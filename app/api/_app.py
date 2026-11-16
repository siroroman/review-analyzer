import hmac
import threading
from collections.abc import Awaitable, Callable
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from itertools import count
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Path, Query, Request, Response
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import AwareDatetime, BaseModel, Field

from app.api._limits import DailyCounter, SlidingWindow
from app.api._types import ApiConfig, Reporter
from app.domain import Clock, Company, Insight, Metrics, Place, Review, RunStatus, Source
from app.gateway import CallStatus, ServiceCall
from app.places import (
    InvalidCompany,
    PlaceNotFound,
    Places,
    PlacesUnavailable,
)
from app.queue import Queue
from app.storage import CallFilter, RunRecord, Storage, UnknownRun
from app.taxonomy import UNCLASSIFIED_KEY

_TEXT = r"^[\w\s.,'&/()\-]+$"  # letters (any language), digits, spaces and a little punctuation
_PLACE_ID = r"^[A-Za-z0-9_\-]+$"
_PUBLIC = {"/openapi.json", "/docs", "/docs/oauth2-redirect", "/redoc"}
_FINISHED = (RunStatus.DONE, RunStatus.PARTIAL)


class SuggestionOut(BaseModel):
    place_id: str
    text: str


class BranchOut(BaseModel):
    place_id: str
    name: str
    address: str


class RunIn(BaseModel):
    place_ids: list[Annotated[str, Field(min_length=1, max_length=300, pattern=_PLACE_ID)]] = Field(
        min_length=1, max_length=20
    )


class RunOut(BaseModel):
    run_id: str
    status: RunStatus
    reused: bool = False


class StepCostOut(BaseModel):
    """What the Run's Service calls cost in each step; `None` for a step that has not started."""

    downloading: Decimal | None
    classifying: Decimal | None
    analysis: Decimal | None


class StatusOut(BaseModel):
    """Progress of a Run: counts and costs only, never a Review or its text. `None` means not known yet."""

    run_id: str
    status: RunStatus
    finished: bool
    cost: Decimal  # the sum of the Run's Service calls so far
    budget: Decimal  # the Run's Budget cap
    downloaded: dict[Source, int] | None  # stored Reviews per Source of the Company's Places
    flagged: int | None  # Flagged Reviews, excluded from the analysis
    classified: int | None  # Reviews with a real ReviewTopic for the latest Taxonomy
    to_classify: int | None  # Reviews to classify: stored, not Flagged
    step_cost: StepCostOut


class TopicOut(BaseModel):
    key: str
    name: str  # the display name of the Topic


class ResultOut(BaseModel):
    run_id: str
    status: RunStatus
    company: Company
    metrics: Metrics
    insights: list[Insight]
    topics: list[TopicOut]  # a name for every `topic_key` the metrics mention
    reviews: int
    flagged: int
    unclassified: int
    cost: Decimal
    # What to know about how the result was made; `industry_fallback`: the industry could not be inferred
    # and the generic Taxonomy was used.
    notes: list[str]


class SpendOut(BaseModel):
    month_total: Decimal  # every Service call of the current calendar month (UTC)
    monthly_cap: Decimal
    share_of_cap: Decimal  # month_total / monthly_cap, 1 means the cap is used up
    by_service: dict[str, Decimal]
    by_day: dict[date, Decimal]
    by_run: dict[str, Decimal]


class CallOut(BaseModel):
    service: str
    operation: str
    run_id: str
    status: CallStatus
    cost: Decimal
    unit: str
    units: int
    latency_ms: int
    error_kind: str | None
    at: datetime


class CallsOut(BaseModel):
    total: int  # matching calls, before the page is cut
    items: list[CallOut]


def _call_out(call: ServiceCall) -> CallOut:
    return CallOut(
        service=call.service,
        operation=call.operation,
        run_id=call.run_id,
        status=call.status,
        cost=call.cost,
        unit=call.unit,
        units=call.units,
        latency_ms=int(call.latency.total_seconds() * 1000),
        error_kind=call.error_kind,
        at=call.at,
    )


def _equal(given: str, expected: str) -> bool:
    return hmac.compare_digest(given.encode(), expected.encode())


def create_app(
    *, storage: Storage, places: Places, queue: Queue, pipeline: Reporter, clock: Clock, config: ApiConfig
) -> FastAPI:
    """The HTTP layer: it parses a request, calls a module and serializes the answer; no business logic."""
    app = FastAPI(title="Review Analyzer API")
    bearer = HTTPBearer(auto_error=False)
    window = SlidingWindow(clock, config.requests_per_minute, timedelta(minutes=1))
    daily = DailyCounter(clock, config.runs_per_day)
    # `Budget` and a database connection are not thread-safe, and the daily limit is a check then a count:
    # the endpoints (run in a thread pool) take this lock for the whole of their work.
    work = threading.Lock()
    search_ids = count(1)

    def search_run() -> str:
        """A new id for each search or confirm, so no shared Budget bucket fills up for good."""
        return f"{config.autocomplete_run_id}-{next(search_ids)}"

    @app.middleware("http")
    async def gate(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        if request.url.path in _PUBLIC:
            return await call_next(request)
        wait = window.hit(request.client.host if request.client else "unknown")
        if wait is not None:
            seconds = str(int(wait.total_seconds()) + 1)
            return JSONResponse({"detail": "too many requests"}, 429, {"Retry-After": seconds})
        if request.url.path == "/admin" or request.url.path.startswith("/admin/"):
            token = _bearer(request.headers.get("Authorization"))
            expected = config.admin_token.get_secret_value() if config.admin_token else None
            if token is None or expected is None or not _equal(token, expected):
                return JSONResponse({"detail": "unauthorized"}, 401)
        return await call_next(request)

    def demo_token(credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)]) -> str:
        """The Demo token of the request, or 401. Returns the token's position, never the token."""
        given = credentials.credentials if credentials else None
        if given is not None:
            for index, token in enumerate(config.demo_tokens):
                if _equal(given, token.get_secret_value()):
                    return str(index)
        raise HTTPException(401, "unauthorized")

    Demo = Annotated[str, Depends(demo_token)]

    @app.get("/places/suggest")
    def suggest(
        _: Demo, q: Annotated[str, Query(min_length=1, max_length=100, pattern=_TEXT)]
    ) -> list[SuggestionOut]:
        with work:
            found = _unavailable(lambda: places.suggest(q, run_id=search_run()))
        return [SuggestionOut(place_id=item.place_id, text=item.text) for item in found]

    @app.get("/places/{place_id}/branches")
    def branches(
        _: Demo, place_id: Annotated[str, Path(min_length=1, max_length=300, pattern=_PLACE_ID)]
    ) -> list[BranchOut]:
        with work:
            found = _unavailable(lambda: _branches(places, place_id, search_run()))
        return [BranchOut(place_id=item.external_id, name=item.name, address=item.address) for item in found]

    @app.post("/runs")
    def create_run(token: Demo, body: RunIn, response: Response) -> RunOut:
        with work:
            if daily.exhausted(token):
                raise HTTPException(429, "daily limit of Runs reached")
            company = _unavailable(lambda: _confirm(places, body, search_run()))
            stored = storage.companies.get_or_create(company)
            fresh = storage.runs.fresh_for(stored.id, config.cache_ttl)
            if fresh is not None:
                return RunOut(run_id=fresh.id, status=fresh.status, reused=True)
            record = storage.runs.create(stored.id, Decimal(config.run_cap))
            daily.count(token)
            queue.enqueue(record.id)
            response.status_code = 202
            return RunOut(run_id=record.id, status=record.status)

    @app.get("/runs/{run_id}")
    def run_status(_: Demo, run_id: str) -> StatusOut:
        with work:
            return _status(storage, _run(storage, run_id))

    @app.get("/runs/{run_id}/result")
    def run_result(_: Demo, run_id: str) -> ResultOut:
        with work:
            record = _run(storage, run_id)
            if record.status not in _FINISHED:
                raise HTTPException(409, f"the Run is {record.status.value}")
            try:
                report = pipeline.report(run_id)
            except UnknownRun as unknown:
                raise HTTPException(404, "unknown Run") from unknown
        return ResultOut(
            run_id=run_id,
            status=report.status,
            company=report.company,
            metrics=report.metrics,
            insights=list(report.insights),
            topics=[TopicOut(key=topic.key, name=topic.name) for topic in report.topics],
            reviews=report.result.reviews,
            flagged=report.result.flagged,
            unclassified=report.result.unclassified,
            cost=report.result.cost,
            notes=list(report.result.notes),
        )

    @app.get(
        "/admin/spend",
        summary="Spend per service, day and Run, and the share of the monthly cap used",
        description="Admin token only (`Authorization: Bearer <admin token>`); a Demo token gives 401.",
        responses={401: {"description": "Missing or wrong Admin token"}},
    )
    def admin_spend(since: AwareDatetime | None = None, until: AwareDatetime | None = None) -> SpendOut:
        where = CallFilter(since=since, until=until)
        now = clock.now().astimezone(UTC)
        with work:
            month_total = storage.calls.total(date(now.year, now.month, 1))
            return SpendOut(
                month_total=month_total,
                monthly_cap=config.monthly_cap,
                share_of_cap=month_total / config.monthly_cap,
                by_service=storage.calls.cost_by_service(where),
                by_day=storage.calls.cost_by_day(where),
                by_run=storage.calls.cost_by_run(where),
            )

    @app.get(
        "/admin/calls",
        summary="The Call log, oldest first, with filters and pagination",
        description="Admin token only (`Authorization: Bearer <admin token>`); a Demo token gives 401. "
        "No request or response bodies are stored or shown. `since <= at < until`.",
        responses={401: {"description": "Missing or wrong Admin token"}},
    )
    def admin_calls(
        service: str | None = None,
        operation: str | None = None,
        run_id: str | None = None,
        status: CallStatus | None = None,
        since: AwareDatetime | None = None,
        until: AwareDatetime | None = None,
        limit: Annotated[int, Query(ge=1, le=500)] = 50,
        offset: Annotated[int, Query(ge=0)] = 0,
    ) -> CallsOut:
        where = CallFilter(
            service=service, operation=operation, run_id=run_id, status=status, since=since, until=until
        )
        with work:
            found = storage.calls.query(where)
        return CallsOut(total=len(found), items=[_call_out(c) for c in found[offset : offset + limit]])

    return app


def _bearer(header: str | None) -> str | None:
    scheme, _, token = (header or "").partition(" ")
    return token.strip() if scheme.lower() == "bearer" and token.strip() else None


def _run(storage: Storage, run_id: str) -> RunRecord:
    record = storage.runs.get(run_id)
    if record is None:
        raise HTTPException(404, "unknown Run")
    return record


def _status(storage: Storage, record: RunRecord) -> StatusOut:
    """Progress from what is stored: Reviews, ReviewTopics and the Call log. Makes no paid call."""
    calls = storage.calls.query(CallFilter(run_id=record.id))

    def out(
        downloaded: dict[Source, int] | None = None,
        flagged: int | None = None,
        classified: int | None = None,
        to_classify: int | None = None,
    ) -> StatusOut:
        return StatusOut(
            run_id=record.id,
            status=record.status,
            finished=record.finished_at is not None,
            cost=sum((c.cost for c in calls), Decimal(0)),
            budget=record.budget_cap,
            downloaded=downloaded,
            flagged=flagged,
            classified=classified,
            to_classify=to_classify,
            step_cost=_step_cost(record, calls),
        )

    stored = storage.companies.by_id(record.company_id)
    if record.status is RunStatus.QUEUED or stored is None:
        return out()
    reviews = {
        place: storage.reviews.list_for_place(place.source, place.external_id)
        for place in stored.company.places
    }
    downloaded: dict[Source, int] = {}
    for place, found in reviews.items():
        downloaded[place.source] = downloaded.get(place.source, 0) + len(found)
    flagged = sum(r.flagged for found in reviews.values() for r in found)
    reached = record.classifying_at or record.analyzing_at or record.status is RunStatus.DONE
    if not reached:
        return out(downloaded, flagged)
    to_classify = sum(1 for found in reviews.values() for r in found if not r.flagged)
    return out(
        downloaded,
        flagged,
        _classified(storage, record.industry or stored.company.industry, reviews),
        to_classify,
    )


def _classified(storage: Storage, industry: str | None, reviews: dict[Place, list[Review]]) -> int:
    taxonomy = None if industry is None else storage.taxonomies.latest(industry)
    if taxonomy is None:
        return 0
    done = 0
    for place, found in reviews.items():
        unflagged = {r.external_id for r in found if not r.flagged}
        topics = storage.reviews.topics_for_place(place.source, place.external_id, taxonomy)
        done += len({t.review_external_id for t in topics if t.topic_key != UNCLASSIFIED_KEY} & unflagged)
    return done


def _step_cost(record: RunRecord, calls: list[ServiceCall]) -> StepCostOut:
    """Price each step by when its calls were made: a step runs from its start to the next one's."""
    if record.status is RunStatus.QUEUED:
        return StepCostOut(downloading=None, classifying=None, analysis=None)
    downloading_end = record.classifying_at or record.analyzing_at or record.finished_at
    classifying_end = record.analyzing_at or record.finished_at

    def cost(start: datetime | None, end: datetime | None) -> Decimal:
        return sum(
            (c.cost for c in calls if (start is None or c.at >= start) and (end is None or c.at < end)),
            Decimal(0),
        )

    return StepCostOut(
        downloading=cost(None, downloading_end),
        classifying=None if record.classifying_at is None else cost(record.classifying_at, classifying_end),
        analysis=None if record.analyzing_at is None else cost(record.analyzing_at, None),
    )


def _confirm(places: Places, body: RunIn, run_id: str) -> Company:
    try:
        return places.confirm(body.place_ids, run_id=run_id)
    except InvalidCompany as invalid:
        raise HTTPException(422, str(invalid)) from invalid
    except PlaceNotFound as missing:
        raise HTTPException(422, "unknown place") from missing


def _branches(places: Places, place_id: str, run_id: str) -> list[Place]:
    try:
        return places.branches(places.resolve(place_id, run_id=run_id), run_id=run_id)
    except PlaceNotFound as missing:
        raise HTTPException(404, "unknown place") from missing


def _unavailable[T](call: Callable[[], T]) -> T:
    try:
        return call()
    except PlacesUnavailable as unavailable:
        headers = (
            {"Retry-After": str(int(unavailable.retry_after.total_seconds()) + 1)}
            if unavailable.retry_after
            else None
        )
        raise HTTPException(503, "places unavailable, try later", headers) from unavailable
