"""The real providers registered in the allow-list: priced, budgeted and reached only through the Gateway."""

from datetime import timedelta
from decimal import Decimal

import pytest
from pydantic import SecretStr

from app.domain import FakeClock
from app.gateway import (
    AnthropicClient,
    BudgetExceeded,
    FakeCallLog,
    Gateway,
    GatewayConfig,
    OpenRouterClient,
    ServicePolicy,
)
from app.llm import FakeSleeper, FakeTracer, Llm, LlmConfig, ModelRef, Route
from app.transport import FakeTransport, HttpResponse
from tests.adapters.helpers import Verdict, fixture
from tests.llm.helpers import START

POLICY = ServicePolicy(frozenset({"complete"}), 100, timedelta(seconds=60), 4)
JEV = ModelRef("openrouter", "jev-1.14")
HAIKU = ModelRef("anthropic", "claude-haiku")


def build(
    openrouter: FakeTransport, anthropic: FakeTransport, run_cap: str = "5"
) -> tuple[Llm, FakeCallLog, FakeTracer]:
    clock = FakeClock(START)
    log = FakeCallLog()
    tracer = FakeTracer()
    gateway = Gateway(
        GatewayConfig({"openrouter": POLICY, "anthropic": POLICY}, Decimal(run_cap)),
        {
            "openrouter": OpenRouterClient(SecretStr("k1"), openrouter, {"jev-1.14": "typesafe/jev-1.14"}),
            "anthropic": AnthropicClient(
                SecretStr("k2"), anthropic, {"claude-haiku": "claude-haiku-5-5", "claude-sonnet": "x"}
            ),
        },
        clock,
        log,
    )
    llm = Llm(LlmConfig({"classify": Route(JEV, HAIKU)}), gateway, clock, FakeSleeper(clock), tracer)
    return llm, log, tracer


def test_a_classify_call_runs_through_the_gateway_to_jev_and_is_priced_and_logged() -> None:
    openrouter = FakeTransport(fixture("openrouter_decisions_ok.json"))
    llm, log, tracer = build(openrouter, FakeTransport())
    result = llm.complete("classify", "Pokoj byl špinavý.", Verdict, run_id="run-1")
    assert result == Verdict(sentiment="negative", injection=False)
    (call,) = log.calls
    assert (call.service, call.operation, call.status, call.unit, call.units) == (
        "openrouter",
        "complete",
        "ok",
        "token",
        418,
    )
    # 412 in * 0.10 + 6 out * 0.30 USD per million tokens (placeholder price table).
    assert call.cost == Decimal("0.0000430")
    (event,) = tracer.events
    assert (event.input_tokens, event.output_tokens, event.cost) == (412, 6, call.cost)


def test_a_refusal_of_jev_falls_back_to_haiku_through_the_gateway() -> None:
    openrouter = FakeTransport(fixture("openrouter_decisions_refusal.json"))
    anthropic = FakeTransport(fixture("anthropic_messages_ok.json"))
    llm, log, _ = build(openrouter, anthropic)
    assert llm.complete("classify", "x", Verdict, run_id="run-1") == Verdict(
        sentiment="negative", injection=False
    )
    assert [(c.service, c.status, c.error_kind) for c in log.calls] == [
        ("openrouter", "failed", "refusal"),
        ("anthropic", "ok", None),
    ]
    assert log.calls[0].cost > 0  # the refused call was charged and is booked


def test_a_run_over_its_budget_never_reaches_the_provider() -> None:
    anthropic = FakeTransport()
    llm, log, _ = build(FakeTransport(HttpResponse(500, b"")), anthropic, run_cap="0.0000001")
    with pytest.raises(BudgetExceeded):
        llm.complete("classify", "x" * 3000, Verdict, run_id="run-1")
    assert anthropic.requests == []
    assert [c.status for c in log.calls] == ["denied"]
