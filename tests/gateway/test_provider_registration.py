"""The real providers registered in the allow-list: priced, budgeted and reached only through the Gateway."""

from datetime import timedelta
from decimal import Decimal

import pytest
from pydantic import SecretStr

from app.domain import FakeClock
from app.gateway import (
    BudgetExceeded,
    ClientError,
    FakeCallLog,
    Gateway,
    GatewayConfig,
    OpenRouterChatClient,
    OpenRouterClient,
    ServicePolicy,
)
from app.llm import FakeSleeper, FakeTracer, Llm, LlmConfig, ModelRef, Route
from app.transport import FakeTransport, HttpResponse
from tests.adapters.helpers import Verdict, fixture
from tests.llm.helpers import START

POLICY = ServicePolicy(frozenset({"complete"}), 100, timedelta(seconds=60), 4)
JEV = ModelRef("openrouter", "jev-1.14")
DEEPSEEK = ModelRef("openrouter_chat", "deepseek-v4.1-flash")


def build(
    jev: FakeTransport, deepseek: FakeTransport, run_cap: str = "5"
) -> tuple[Llm, FakeCallLog, FakeTracer]:
    clock = FakeClock(START)
    log = FakeCallLog()
    tracer = FakeTracer()
    gateway = Gateway(
        GatewayConfig({"openrouter": POLICY, "openrouter_chat": POLICY}, Decimal(run_cap)),
        {
            "openrouter": OpenRouterClient(SecretStr("k1"), jev, {"jev-1.14": "typesafe/jev-1.14"}),
            "openrouter_chat": OpenRouterChatClient(
                SecretStr("k1"), deepseek, {"deepseek-v4.1-flash": "deepseek/deepseek-v4.1-flash"}
            ),
        },
        clock,
        log,
    )
    config = LlmConfig({"classify": Route(JEV), "propose": Route(DEEPSEEK)}, max_retries=0)
    return Llm(config, gateway, clock, FakeSleeper(clock), tracer), log, tracer


def test_a_classify_call_runs_through_the_gateway_to_jev_and_is_priced_and_logged() -> None:
    jev = FakeTransport(fixture("openrouter_decisions_ok.json"))
    llm, log, tracer = build(jev, FakeTransport())
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


def test_a_propose_call_runs_through_the_gateway_to_deepseek_and_is_priced_and_logged() -> None:
    deepseek = FakeTransport(fixture("openrouter_chat_ok.json"))
    llm, log, _ = build(FakeTransport(), deepseek)
    result = llm.complete("propose", "<reviews>[]</reviews>", Verdict, run_id="run-1")
    assert result == Verdict(sentiment="negative", injection=False)
    (call,) = log.calls
    assert (call.service, call.operation, call.status, call.units) == (
        "openrouter_chat",
        "complete",
        "ok",
        194,
    )
    # 180 in * 0.30 + 14 out * 1.20 USD per million tokens (placeholder price table).
    assert call.cost == Decimal("0.0000708")


def test_a_refusal_of_jev_fails_the_call_and_no_other_model_is_asked() -> None:
    jev = FakeTransport(fixture("openrouter_decisions_refusal.json"))
    deepseek = FakeTransport(fixture("openrouter_chat_ok.json"))
    llm, log, _ = build(jev, deepseek)
    with pytest.raises(ClientError) as failure:
        llm.complete("classify", "x", Verdict, run_id="run-1")
    assert failure.value.kind == "refusal"
    assert [(c.service, c.status, c.error_kind) for c in log.calls] == [("openrouter", "failed", "refusal")]
    assert deepseek.requests == []
    assert log.calls[0].cost > 0  # the refused call was charged and is booked


def test_a_run_over_its_budget_never_reaches_the_provider() -> None:
    deepseek = FakeTransport()
    llm, log, _ = build(FakeTransport(), deepseek, run_cap="0.0000001")
    with pytest.raises(BudgetExceeded):
        llm.complete("propose", "x" * 3000, Verdict, run_id="run-1")
    assert deepseek.requests == []
    assert [c.status for c in log.calls] == ["denied"]


def test_a_failed_http_call_is_booked_and_unpaid() -> None:
    llm, log, _ = build(FakeTransport(), FakeTransport(HttpResponse(500, b"")))
    with pytest.raises(ClientError):
        llm.complete("propose", "x", Verdict, run_id="run-1")
    assert [(c.status, c.error_kind) for c in log.calls] == [("failed", "server_error")]


def _deepseek_llm(transport: FakeTransport, max_output: int, run_cap: str) -> Llm:
    clock = FakeClock(START)
    gateway = Gateway(
        GatewayConfig({"openrouter_chat": POLICY}, Decimal(run_cap)),
        {
            "openrouter_chat": OpenRouterChatClient(
                SecretStr("k1"),
                transport,
                {"deepseek-v4.1-flash": "deepseek/deepseek-v4.1-flash"},
                max_output_tokens=max_output,
            )
        },
        clock,
        FakeCallLog(),
    )
    return Llm(
        LlmConfig({"propose": Route(DEEPSEEK)}, max_retries=0),
        gateway,
        clock,
        FakeSleeper(clock),
        FakeTracer(),
    )


def test_the_output_limit_of_deepseek_is_reserved_in_the_budget_before_the_call() -> None:
    # 12288 tokens out at 1.20 USD per million reserve 0.0147 USD: over a 0.01 USD cap, nothing is sent;
    # the default limit of 4096 tokens reserves 0.0049 USD and goes through.
    refused = FakeTransport(fixture("openrouter_chat_ok.json"))
    with pytest.raises(BudgetExceeded):
        _deepseek_llm(refused, 12288, "0.01").complete(
            "propose", "<reviews>[]</reviews>", Verdict, run_id="run-1"
        )
    assert refused.requests == []

    allowed = FakeTransport(fixture("openrouter_chat_ok.json"))
    _deepseek_llm(allowed, 4096, "0.01").complete("propose", "<reviews>[]</reviews>", Verdict, run_id="run-1")
    assert len(allowed.requests) == 1
