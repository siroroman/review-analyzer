import base64
import logging
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from pydantic import SecretStr

from app.domain import FakeClock
from app.llm import TraceEvent, Tracer
from app.tracing import FakeIds, LangfuseConfig, LangfuseTracer, UuidIds
from app.transport import FakeTransport, HttpError, HttpResponse, HttpTimeout
from tests.adapters.helpers import body_of, fixture

PUBLIC, SECRET = "pk-lf-public-1", "sk-lf-secret-9999"
NOW = datetime(2026, 11, 12, 9, 0, 0, tzinfo=UTC)
CONFIG = LangfuseConfig("https://cloud.langfuse.example", SecretStr(PUBLIC), SecretStr(SECRET))


def event(outcome: str = "ok", cost: str = "0.0042") -> TraceEvent:
    return TraceEvent(
        task="classify",
        service="openrouter",
        model="jev-1.14",
        input_tokens=412,
        output_tokens=6,
        cost=Decimal(cost),
        latency=timedelta(milliseconds=250),
        outcome=outcome,  # type: ignore[arg-type]
    )


def tracer(*steps: HttpResponse | HttpError) -> tuple[Tracer, FakeTransport]:
    transport = FakeTransport(*steps)
    return LangfuseTracer(CONFIG, transport, FakeClock(NOW), FakeIds()), transport


def test_records_tokens_and_price_of_the_call_as_a_generation() -> None:
    langfuse, transport = tracer(fixture("langfuse_ingestion_207.json", 207))
    langfuse.trace(event())
    sent = transport.requests[0]
    assert sent.url == "https://cloud.langfuse.example/api/public/ingestion"
    batch = body_of(sent.body)["batch"]
    assert isinstance(batch, list) and len(batch) == 1
    item = batch[0]
    assert item["type"] == "generation-create"
    assert item["timestamp"] == "2026-11-12T09:00:00Z"
    generation = item["body"]
    assert generation["name"] == "classify"
    assert generation["model"] == "jev-1.14"
    assert generation["usageDetails"] == {"input": 412, "output": 6, "total": 418}
    assert generation["costDetails"] == {"total": 0.0042}
    assert generation["startTime"] == "2026-11-12T08:59:59.750000Z"
    assert generation["endTime"] == "2026-11-12T09:00:00Z"
    assert generation["metadata"] == {"service": "openrouter", "outcome": "ok"}
    assert "level" not in generation


def test_authenticates_with_the_keys_as_basic_auth() -> None:
    langfuse, transport = tracer(fixture("langfuse_ingestion_207.json", 207))
    langfuse.trace(event())
    expected = base64.b64encode(f"{PUBLIC}:{SECRET}".encode()).decode()
    assert transport.requests[0].headers["Authorization"] == f"Basic {expected}"


@pytest.mark.parametrize("outcome", ["invalid", "error"])
def test_a_failed_call_is_an_error_level_generation_with_zero_cost(outcome: str) -> None:
    langfuse, transport = tracer(fixture("langfuse_ingestion_207.json", 207))
    langfuse.trace(event(outcome, "0"))
    batch = body_of(transport.requests[0].body)["batch"]
    assert isinstance(batch, list)
    generation = batch[0]["body"]
    assert generation["level"] == "ERROR"
    assert generation["statusMessage"] == outcome
    assert generation["costDetails"] == {"total": 0.0}


def test_each_call_gets_its_own_ids() -> None:
    langfuse, transport = tracer(
        fixture("langfuse_ingestion_207.json", 207), fixture("langfuse_ingestion_207.json", 207)
    )
    langfuse.trace(event())
    langfuse.trace(event())
    ids = []
    for sent in transport.requests:
        batch = body_of(sent.body)["batch"]
        assert isinstance(batch, list)
        ids += [batch[0]["id"], batch[0]["body"]["id"]]
    assert len(set(ids)) == 4


@pytest.mark.parametrize(
    "step",
    [
        HttpTimeout("timeout"),
        HttpError("connection failed"),
        HttpResponse(401, b"Unauthorized"),
        HttpResponse(500, b"boom"),
        fixture("langfuse_ingestion_error.json", 207),
        HttpResponse(207, b"not json"),
    ],
)
def test_a_failing_langfuse_never_breaks_the_call_and_the_log_holds_no_key(
    step: HttpResponse | HttpError, caplog: pytest.LogCaptureFixture
) -> None:
    langfuse, _ = tracer(step)
    with caplog.at_level(logging.DEBUG):
        langfuse.trace(event())
    assert "langfuse" in caplog.text.lower()
    assert PUBLIC not in caplog.text and SECRET not in caplog.text
    assert "invalid body" not in caplog.text


def test_the_keys_are_not_in_the_config_or_tracer_repr() -> None:
    langfuse, _ = tracer()
    shown = repr(CONFIG) + repr(langfuse) + str(langfuse.__dict__)
    assert PUBLIC not in shown and SECRET not in shown


def test_the_config_is_read_from_the_environment_only() -> None:
    config = LangfuseConfig.from_environ(
        {
            "LANGFUSE_HOST": "https://eu.example/",
            "LANGFUSE_PUBLIC_KEY": PUBLIC,
            "LANGFUSE_SECRET_KEY": SECRET,
        }
    )
    assert config.host == "https://eu.example"
    assert config.public_key.get_secret_value() == PUBLIC


def test_ids_are_unique_without_a_test_source() -> None:
    ids = UuidIds()
    assert ids.new_id() != ids.new_id()
