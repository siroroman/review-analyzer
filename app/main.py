"""Entrypoint: the one place that sees every module. It reads the environment and wires the real adapters
behind the ports (ADR-0004, ADR-0006) into the API app and the worker app. Google Maps is the only Source.

Run with `uvicorn --factory app.main:api_app` and `uvicorn --factory app.main:worker_app`, or
both and the built web as one service with `uvicorn --factory app.main:service_app` (the container image).
Without the CLOUD_TASKS_* settings the API hands Runs to an in-process `LocalQueue` and needs no worker app.
"""

import json
import os
import threading
import time
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

from fastapi import FastAPI
from pydantic import SecretStr
from starlette.exceptions import HTTPException
from starlette.responses import PlainTextResponse, Response
from starlette.staticfiles import StaticFiles
from starlette.types import ASGIApp, Receive, Scope, Send

from app.api import ApiConfig, create_app
from app.classification import Classifier
from app.domain import Clock, Source, SystemRandom
from app.gateway import (
    GOOGLE_PLACES,
    SCRAPE_GOOGLE_REVIEWS,
    AnthropicClient,
    Gateway,
    GatewayConfig,
    GooglePlacesClient,
    ServiceClient,
    ServicePolicy,
    YasogaNClient,
)
from app.insights import InsightGenerator
from app.llm import Llm, LlmConfig, ModelRef, Route
from app.pipeline import Pipeline, PipelineConfig
from app.places import NoOtherSource, Places
from app.queue import CloudTasksConfig, CloudTasksQueue, LocalQueue, Queue, QueueError
from app.sanitize import PatternInjectionDetector
from app.sources import Sources
from app.storage import Storage, postgres_storage
from app.taxonomy import Taxonomies
from app.tracing import LangfuseConfig, LangfuseTracer, UuidIds
from app.transport import HttpError, HttpRequest, HttpTransport, UrllibTransport, read_secret
from app.worker import GoogleTokenVerifier, TokenVerifier, Worker, auth_from_env, create_worker_app

# Cloud Tasks is used when any of these is set (then all must be); with none set, `LocalQueue` is used.
CLOUD_TASKS_VARIABLES = (
    "CLOUD_TASKS_PROJECT",
    "CLOUD_TASKS_LOCATION",
    "CLOUD_TASKS_QUEUE",
    "WORKER_URL",
    "WORKER_SERVICE_ACCOUNT",
)

# The names of the environment variables this module reads: `.env.example` lists each of them.
SECRET_VARIABLES = (
    "DATABASE_URL",
    "GOOGLE_PLACES_API_KEY",
    "ANTHROPIC_API_KEY",
    "LANGFUSE_PUBLIC_KEY",
    "LANGFUSE_SECRET_KEY",
    "DEMO_TOKENS",
)
SETTING_VARIABLES = (
    "ADMIN_TOKEN",
    "YASOGAN_URL",
    "LANGFUSE_HOST",
    *CLOUD_TASKS_VARIABLES,
)

_ANTHROPIC = "anthropic"
_YASOGAN = "yasogan"
_HAIKU = ModelRef(_ANTHROPIC, "claude-haiku")
_SONNET = ModelRef(_ANTHROPIC, "claude-sonnet")
_MODEL_IDS = {"claude-haiku": "claude-haiku-5-5", "claude-sonnet": "claude-sonnet-5-5"}
_REVIEWS_PER_PLACE = 1000  # ADR-0008: the input limit for Google Maps
_TOKEN_URL = "http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/token"  # noqa: S105
_TOKEN_MARGIN = timedelta(seconds=60)


class SystemClock:
    """The real `Clock`: the one place that reads the time of the machine."""

    def now(self) -> datetime:
        return datetime.now(UTC)  # noqa: TID251 - this is the Clock adapter itself (ADR-0004)


class ThreadSleeper:
    """The real `Sleeper` of `llm` and `pipeline`: blocks the calling thread."""

    def sleep(self, delay: timedelta) -> None:
        time.sleep(delay.total_seconds())  # noqa: TID251 - this is the Sleeper adapter itself (ADR-0004)


class MetadataToken:
    """The access token of the service account of this Cloud Run service, read from the metadata server.

    Cached until a minute before it expires. Raises `QueueError` when no token can be had: its only
    caller is the queue.
    """

    def __init__(self, transport: HttpTransport, clock: Clock) -> None:
        self._transport = transport
        self._clock = clock
        self._lock = threading.Lock()
        self._token: SecretStr | None = None
        self._expires = datetime.min.replace(tzinfo=UTC)

    def __call__(self) -> SecretStr:
        with self._lock:
            if self._token is None or self._clock.now() >= self._expires:
                self._token, self._expires = self._fetch()
            return self._token

    def _fetch(self) -> tuple[SecretStr, datetime]:
        request = HttpRequest("GET", _TOKEN_URL, {"Metadata-Flavor": "Google"}, b"", 5.0)
        try:
            response = self._transport.send(request)
            body = json.loads(response.body)
            token, lifetime = body["access_token"], int(body["expires_in"])
        except (HttpError, ValueError, KeyError, TypeError):
            raise QueueError("no access token from the metadata server") from None
        if response.status != 200 or not isinstance(token, str) or not token:
            raise QueueError("no access token from the metadata server")
        return SecretStr(token), self._clock.now() + timedelta(seconds=lifetime) - _TOKEN_MARGIN


@dataclass(frozen=True)
class Apps:
    """The two HTTP apps of one deployment."""

    api: FastAPI
    worker: FastAPI
    queue: Queue


def _policy(operations: set[str], per_minute: int, concurrent: int) -> ServicePolicy:
    return ServicePolicy(frozenset(operations), per_minute, timedelta(minutes=1), concurrent)


def _cloud_tasks_config(environ: Mapping[str, str]) -> CloudTasksConfig | None:
    """The Cloud Tasks settings, or `None` when none is set (a local run). A half-set group raises
    `MissingSecret` for the first missing variable."""
    if not any(environ.get(name, "").strip() for name in CLOUD_TASKS_VARIABLES):
        return None
    return CloudTasksConfig(
        project=read_secret(environ, "CLOUD_TASKS_PROJECT").get_secret_value(),
        location=read_secret(environ, "CLOUD_TASKS_LOCATION").get_secret_value(),
        queue=read_secret(environ, "CLOUD_TASKS_QUEUE").get_secret_value(),
        worker_url=read_secret(environ, "WORKER_URL").get_secret_value(),
        service_account=read_secret(environ, "WORKER_SERVICE_ACCOUNT").get_secret_value(),
    )


def build_apps(
    environ: Mapping[str, str],
    *,
    transport: HttpTransport | None = None,
    storage: Storage | None = None,
    clock: Clock | None = None,
    token_verifier: TokenVerifier | None = None,
) -> Apps:
    """Wire the API and the worker from `environ`. Raises `MissingSecret` (naming the variable, never its
    value) before anything is connected. Tests pass fakes for `transport`, `storage`, `clock` and
    `token_verifier`."""
    api_config = ApiConfig.from_environ(environ)
    dsn = read_secret(environ, "DATABASE_URL")
    google_key = read_secret(environ, "GOOGLE_PLACES_API_KEY")
    yasogan_url = read_secret(environ, "YASOGAN_URL").get_secret_value()
    anthropic_key = read_secret(environ, "ANTHROPIC_API_KEY")
    langfuse = LangfuseConfig.from_environ(environ)
    tasks = _cloud_tasks_config(environ)

    clock = clock or SystemClock()
    transport = transport or UrllibTransport()
    storage = storage or postgres_storage(dsn.get_secret_value(), clock)

    clients: dict[str, ServiceClient] = {
        GOOGLE_PLACES: GooglePlacesClient(google_key, transport),
        _YASOGAN: YasogaNClient(yasogan_url, transport),
        _ANTHROPIC: AnthropicClient(anthropic_key, transport, _MODEL_IDS),
    }
    gateway = Gateway(
        GatewayConfig(
            {
                GOOGLE_PLACES: _policy({"autocomplete", "details", "text_search"}, 600, 4),
                _YASOGAN: _policy({SCRAPE_GOOGLE_REVIEWS}, 10, 2),
                _ANTHROPIC: _policy({"complete"}, 100, 4),
            },
            run_cap=Decimal(api_config.run_cap),
            monthly_cap=api_config.monthly_cap,
        ),
        clients,
        clock,
        storage.calls,
    )
    sleeper = ThreadSleeper()
    llm = Llm(
        LlmConfig(
            {
                "taxonomy": Route(_HAIKU),
                "classification": Route(_HAIKU),
                "industry": Route(_SONNET),
                "insights": Route(_SONNET),
            }
        ),
        gateway,
        clock,
        sleeper,
        LangfuseTracer(langfuse, transport, clock, UuidIds()),
    )
    pipeline = Pipeline(
        storage=storage,
        sources=Sources(gateway),
        detector=PatternInjectionDetector(),
        taxonomies=Taxonomies(llm, storage.taxonomies, SystemRandom()),
        classifier=Classifier(llm, storage.reviews),
        insights=InsightGenerator(llm),
        sleeper=sleeper,
        config=PipelineConfig(
            reviews_per_place=_REVIEWS_PER_PLACE,
            cache_ttl=api_config.cache_ttl,
            sources=frozenset({Source.GOOGLE_MAPS}),
        ),
    )
    worker = Worker(pipeline)
    queue: Queue = (
        CloudTasksQueue(tasks, transport, MetadataToken(transport, clock))
        if tasks
        else LocalQueue(worker.handle, sleeper.sleep)
    )
    api = create_app(
        storage=storage,
        places=Places(gateway, NoOtherSource()),
        queue=queue,
        pipeline=pipeline,
        clock=clock,
        config=api_config,
    )
    return Apps(
        api=api,
        worker=create_worker_app(
            worker, auth=auth_from_env(environ, token_verifier or GoogleTokenVerifier())
        ),
        queue=queue,
    )


def api_app() -> FastAPI:
    """Factory for `uvicorn --factory app.main:api_app`."""
    return build_apps(os.environ).api


def worker_app() -> FastAPI:
    """Factory for `uvicorn --factory app.main:worker_app`."""
    return build_apps(os.environ).worker


class _Spa(StaticFiles):
    """The built web: a path that is no file is a client route, so it gets `index.html`."""

    async def get_response(self, path: str, scope: Scope) -> Response:
        try:
            response = await super().get_response(path, scope)
        except HTTPException:  # only ever a 404 for a GET: no such file
            if "." in path.rsplit("/", 1)[-1]:  # a missing asset (a stale hash) is a 404, not the page
                return PlainTextResponse("Not Found", status_code=404)
            return await super().get_response("index.html", scope)
        return response


class _Service:
    """One ASGI app for one Cloud Run service: `/api/*` and `/admin/*` to the API (the prefix `/api` is
    stripped, so the API sees the same paths as behind the dev proxy), `/tasks/*` to the worker, anything
    else to the web."""

    def __init__(self, apps: Apps, web: ASGIApp) -> None:
        self._api, self._worker, self._web = apps.api, apps.worker, web

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "lifespan":
            await self._api(scope, receive, send)
            return
        path: str = scope["path"]
        if path == "/api" or path.startswith("/api/"):
            stripped = path[len("/api") :] or "/"
            raw: bytes = scope.get("raw_path") or path.encode()
            await self._api(
                {**scope, "path": stripped, "raw_path": raw[len(b"/api") :] or b"/"}, receive, send
            )
        elif path == "/admin" or path.startswith("/admin/"):
            await self._api(scope, receive, send)
        elif path == "/tasks" or path.startswith("/tasks/"):
            await self._worker(scope, receive, send)
        else:
            await self._web(scope, receive, send)


def build_service(apps: Apps, web_dir: Path) -> ASGIApp:
    """The API, the worker and the built web (`web_dir`, the output of `npm run build`) as one app."""
    return _Service(apps, _Spa(directory=web_dir, html=True))


def service_app() -> ASGIApp:
    """Factory for `uvicorn --factory app.main:service_app`. The built web is in `WEB_DIR`."""
    return build_service(build_apps(os.environ), Path(os.environ.get("WEB_DIR", "web/dist")))
