from datetime import timedelta

from app.gateway import ClientResponse, ClientTimeout, FakeServiceClient, Units
from app.llm import TraceEvent
from tests.llm.helpers import (
    JEV_USAGE,
    VALID,
    Answer,
    D,
    Setup,
    scripted,
)


def test_the_tracer_gets_task_tokens_cost_and_latency_of_a_call() -> None:
    s = Setup(jev=lambda c: scripted(JEV_USAGE, VALID, clock=c, took=timedelta(milliseconds=120)))

    s.llm.complete("classify", "Rate this.", Answer, run_id="run-1")

    assert s.tracer.events == [
        TraceEvent(
            task="classify",
            service="openrouter",
            model="jev-1.14",
            input_tokens=10_000,
            output_tokens=0,
            cost=D("0.001"),
            latency=timedelta(milliseconds=120),
            outcome="ok",
        )
    ]


def test_a_failed_call_is_traced_with_no_tokens_and_no_cost() -> None:
    s = Setup(jev=lambda c: scripted(JEV_USAGE, ClientTimeout(), VALID, clock=c, took=timedelta(seconds=30)))

    s.llm.complete("classify", "Rate this.", Answer, run_id="run-1")

    failed, ok = s.tracer.events
    assert (failed.outcome, failed.input_tokens, failed.output_tokens, failed.cost) == ("error", 0, 0, D(0))
    assert failed.latency == timedelta(seconds=30)
    assert ok.outcome == "ok"


def test_an_invalid_answer_is_traced_with_its_tokens_and_cost() -> None:
    s = Setup(jev=lambda c: scripted(JEV_USAGE, "nope", VALID, clock=c))

    s.llm.complete("classify", "Rate this.", Answer, run_id="run-1")

    invalid, ok = s.tracer.events
    assert (invalid.outcome, invalid.input_tokens, invalid.cost) == ("invalid", 10_000, D("0.001"))
    assert ok.outcome == "ok"


def test_every_attempt_on_every_model_is_traced() -> None:
    s = Setup(jev=lambda c: scripted(JEV_USAGE, "nope", "nope", clock=c))

    s.llm.complete("classify", "Rate this.", Answer, run_id="run-1")

    assert [(e.model, e.outcome) for e in s.tracer.events] == [
        ("jev-1.14", "invalid"),
        ("jev-1.14", "invalid"),
        ("claude-haiku", "ok"),
    ]
    assert s.tracer.events[-1].cost == D("0.2")


def test_usage_in_units_is_traced_with_zero_tokens() -> None:
    # Not a model today, but the trace must not break when a provider reports units.
    units = Units("openrouter", "jev-1.14", 1)
    s = Setup(jev=lambda _c: FakeServiceClient(JEV_USAGE, lambda _op, _req: ClientResponse(VALID, units)))

    s.llm.complete("classify", "Rate this.", Answer, run_id="run-1")

    [event] = s.tracer.events
    assert (event.input_tokens, event.output_tokens, event.outcome) == (0, 0, "ok")
