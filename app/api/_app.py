import hmac
import threading
from collections.abc import Awaitable, Callable
from datetime import timedelta
from decimal import Decimal
from itertools import count
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field

from app.api._limits import DailyCounter, SlidingWindow
from app.api._types import ApiConfig, Reporter
from app.domain import Clock, Company, Insight, Metrics, RunStatus
from app.places import (
    InvalidCompany,
    PlaceNotFound,
    Places,
    PlacesUnavailable,
)
from app.queue import Queue
from app.storage import RunRecord, Storage, UnknownRun

_TEXT = r"^[\w\s.,'&/()\-]+$"  # letters (any language), digits, spaces and a little punctuation
_PLACE_ID = r"^[A-Za-z0-9_\-]+$"
_PUBLIC = {"/openapi.json", "/docs", "/docs/oauth2-redirect", "/redoc"}
_FINISHED = (RunStatus.DONE, RunStatus.PARTIAL)


class SuggestionOut(BaseModel):
    place_id: str
    text: str


class RunIn(BaseModel):
    place_ids: list[Annotated[str, Field(min_length=1, max_length=300, pattern=_PLACE_ID)]] = Field(
        min_length=1, max_length=20
    )
    name: str = Field(min_length=1, max_length=100, pattern=_TEXT)
    industry: str = Field(min_length=1, max_length=60, pattern=_TEXT)


class RunOut(BaseModel):
    run_id: str
    status: RunStatus
    reused: bool = False


class StatusOut(BaseModel):
    run_id: str
    status: RunStatus
    finished: bool


class ResultOut(BaseModel):
    run_id: str
    status: RunStatus
    company: Company
    metrics: Metrics
    insights: list[Insight]
    reviews: int
    flagged: int
    unclassified: int
    cost: Decimal


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
            record = _run(storage, run_id)
        return StatusOut(run_id=record.id, status=record.status, finished=record.finished_at is not None)

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
            reviews=report.result.reviews,
            flagged=report.result.flagged,
            unclassified=report.result.unclassified,
            cost=report.result.cost,
        )

    return app


def _bearer(header: str | None) -> str | None:
    scheme, _, token = (header or "").partition(" ")
    return token.strip() if scheme.lower() == "bearer" and token.strip() else None


def _run(storage: Storage, run_id: str) -> RunRecord:
    record = storage.runs.get(run_id)
    if record is None:
        raise HTTPException(404, "unknown Run")
    return record


def _confirm(places: Places, body: RunIn, run_id: str) -> Company:
    try:
        return places.confirm(body.place_ids, name=body.name, industry=body.industry, run_id=run_id)
    except InvalidCompany as invalid:
        raise HTTPException(422, str(invalid)) from invalid
    except PlaceNotFound as missing:
        raise HTTPException(422, "unknown place") from missing


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
