"""Entrypoint: the one place that sees every module. It reads the environment and wires the real adapters
behind the ports (ADR-0004, ADR-0006) into the API app and the worker app. Google Maps is the only Source.

Run with `uvicorn --factory app.main:api_app` and `uvicorn --factory app.main:worker_app`.
"""

import json
import os
import threading
import time
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from fastapi import FastAPI
from pydantic import SecretStr

from app.api import ApiConfig, create_app
from app.classification import Classifier
from app.domain import Clock, Source
from app.gateway import (
    GOOGLE_PLACES,
    SCRAPE_GOOGLE_REVIEWS,
    AnthropicClient,
    ApifyClient,
    Gateway,
    GatewayConfig,
    GooglePlacesClient,
    ServiceClient,
    ServicePolicy,
)
from app.insights import InsightGenerator
from app.llm import Llm, LlmConfig, ModelRef, Route
from app.pipeline import Pipeline, PipelineConfig
from app.places import NoOtherSource, Places
from app.queue import CloudTasksConfig, CloudTasksQueue, QueueError
from app.sanitize import PatternInjectionDetector
from app.sources import Sources
from app.storage import Storage, postgres_storage
from app.taxonomy import Taxonomies
from app.tracing import LangfuseConfig, LangfuseTracer, UuidIds
from app.transport import HttpError, HttpRequest, HttpTransport, UrllibTransport, read_secret
from app.worker import Worker, create_worker_app

# The names of the environment variables this module reads: `.env.example` lists each of them.
SECRET_VARIABLES = (
    "DATABASE_URL",
    "GOOGLE_PLACES_API_KEY",
    "APIFY_TOKEN",
    "ANTHROPIC_API_KEY",
    "LANGFUSE_PUBLIC_KEY",
    "LANGFUSE_SECRET_KEY",
    "DEMO_TOKENS",
)
SETTING_VARIABLES = (
    "ADMIN_TOKEN",
    "LANGFUSE_HOST",
    "CLOUD_TASKS_PROJECT",
    "CLOUD_TASKS_LOCATION",
    "CLOUD_TASKS_QUEUE",
    "WORKER_URL",
    "WORKER_SERVICE_ACCOUNT",
)

_ANTHROPIC = "anthropic"
_APIFY = "apify"
_HAIKU = ModelRef(_ANTHROPIC, "claude-haiku")
_SONNET = ModelRef(_ANTHROPIC, "claude-sonnet")
_MODEL_IDS = {"claude-haiku": "claude-haiku-5-5", "claude-sonnet": "claude-sonnet-5-5"}
_REVIEWS_PER_PLACE = 100
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


def _policy(operations: set[str], per_minute: int, concurrent: int) -> ServicePolicy:
    return ServicePolicy(frozenset(operations), per_minute, timedelta(minutes=1), concurrent)


def build_apps(
    environ: Mapping[str, str],
    *,
    transport: HttpTransport | None = None,
    storage: Storage | None = None,
    clock: Clock | None = None,
) -> Apps:
    """Wire the API and the worker from `environ`. Raises `MissingSecret` (naming the variable, never its
    value) before anything is connected. Tests pass a fake `transport`, `storage` and `clock`."""
    api_config = ApiConfig.from_environ(environ)
    dsn = read_secret(environ, "DATABASE_URL")
    google_key = read_secret(environ, "GOOGLE_PLACES_API_KEY")
    apify_token = read_secret(environ, "APIFY_TOKEN")
    anthropic_key = read_secret(environ, "ANTHROPIC_API_KEY")
    langfuse = LangfuseConfig.from_environ(environ)
    tasks = CloudTasksConfig(
        project=read_secret(environ, "CLOUD_TASKS_PROJECT").get_secret_value(),
        location=read_secret(environ, "CLOUD_TASKS_LOCATION").get_secret_value(),
        queue=read_secret(environ, "CLOUD_TASKS_QUEUE").get_secret_value(),
        worker_url=read_secret(environ, "WORKER_URL").get_secret_value(),
        service_account=read_secret(environ, "WORKER_SERVICE_ACCOUNT").get_secret_value(),
    )

    clock = clock or SystemClock()
    transport = transport or UrllibTransport()
    storage = storage or postgres_storage(dsn.get_secret_value(), clock)

    clients: dict[str, ServiceClient] = {
        GOOGLE_PLACES: GooglePlacesClient(google_key, transport),
        _APIFY: ApifyClient(apify_token, transport),
        _ANTHROPIC: AnthropicClient(anthropic_key, transport, _MODEL_IDS),
    }
    gateway = Gateway(
        GatewayConfig(
            {
                GOOGLE_PLACES: _policy({"autocomplete", "details", "text_search"}, 600, 4),
                _APIFY: _policy({SCRAPE_GOOGLE_REVIEWS}, 10, 2),
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
        taxonomies=Taxonomies(llm, storage.taxonomies),
        classifier=Classifier(llm, storage.reviews),
        insights=InsightGenerator(llm),
        sleeper=sleeper,
        config=PipelineConfig(
            reviews_per_place=_REVIEWS_PER_PLACE,
            cache_ttl=api_config.cache_ttl,
            sources=frozenset({Source.GOOGLE_MAPS}),
        ),
    )
    api = create_app(
        storage=storage,
        places=Places(gateway, NoOtherSource()),
        queue=CloudTasksQueue(tasks, transport, MetadataToken(transport, clock)),
        pipeline=pipeline,
        clock=clock,
        config=api_config,
    )
    return Apps(api=api, worker=create_worker_app(Worker(pipeline)))


def api_app() -> FastAPI:
    """Factory for `uvicorn --factory app.main:api_app`."""
    return build_apps(os.environ).api


def worker_app() -> FastAPI:
    """Factory for `uvicorn --factory app.main:worker_app`."""
    return build_apps(os.environ).worker
