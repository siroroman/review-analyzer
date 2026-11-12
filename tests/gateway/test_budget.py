from datetime import date, timedelta

import pytest

from app.gateway import BudgetExceeded, ClientResponse, FakeServiceClient, GatewayDenied, Tokens, Units
from tests.gateway.helpers import HAIKU_700K, D, Setup, policy

HAIKU_1_4 = Tokens("anthropic", "claude-haiku", 400_000, 200_000)  # 0.4 + 1.0 = 1.4 USD


def test_a_call_that_ends_exactly_at_the_monthly_cap_is_allowed_the_next_is_not() -> None:
    s = Setup(monthly_cap="0.7")

    s.gateway.call("anthropic", "complete", "x", run_id="run-1")  # 0.7 of 0.7

    with pytest.raises(BudgetExceeded) as exceeded:
        s.gateway.call("anthropic", "complete", "x", run_id="run-2")
    assert exceeded.value.cap_kind == "monthly"
    assert len(s.clients["anthropic"].calls) == 1


def test_one_cent_over_the_monthly_cap_is_refused_before_the_call_and_logged() -> None:
    s = Setup(monthly_cap="0.69")

    with pytest.raises(BudgetExceeded):
        s.gateway.call("anthropic", "complete", "x", run_id="run-1")

    assert s.clients["anthropic"].calls == []
    [call] = s.log.calls
    assert (call.status, call.error_kind, call.cost) == ("denied", "budget_exceeded", D(0))


def test_the_run_cap_stops_a_run_but_not_another_run() -> None:
    s = Setup(run_cap="1")

    s.gateway.call("anthropic", "complete", "x", run_id="run-1")  # 0.7
    with pytest.raises(BudgetExceeded) as exceeded:
        s.gateway.call("anthropic", "complete", "x", run_id="run-1")
    s.gateway.call("anthropic", "complete", "x", run_id="run-2")

    assert exceeded.value.cap_kind == "run"


def test_a_paid_call_is_in_the_monthly_total_before_the_next_reserve() -> None:
    # Budget.record does not add to the monthly total itself: the gateway must have written the Service
    # call to the Call log (the MonthlySpend) before the next reserve. Two 0.7 USD calls break a 1 USD cap.
    s = Setup(monthly_cap="1")

    s.gateway.call("anthropic", "complete", "x", run_id="run-1")

    assert s.log.total(date(2026, 11, 1)) == D("0.7")
    with pytest.raises(BudgetExceeded):
        s.gateway.call("anthropic", "complete", "x", run_id="run-2")


def test_the_actual_cost_above_the_estimate_is_booked_and_logged() -> None:
    client = FakeServiceClient(HAIKU_700K, lambda *_: ClientResponse("answer", HAIKU_1_4))
    s = Setup(clients={"anthropic": client}, monthly_cap="2")

    response = s.gateway.call("anthropic", "complete", "x", run_id="run-1")

    assert response.cost == D("1.4")
    assert s.log.calls[0].cost == D("1.4")
    with pytest.raises(BudgetExceeded):  # 1.4 spent + 0.7 estimated > 2
        s.gateway.call("anthropic", "complete", "x", run_id="run-2")


def test_a_service_or_unit_without_a_price_is_denied_and_never_called() -> None:
    unpriced = Units("apify", "mystery_item", 5)
    client = FakeServiceClient(unpriced, lambda *_: ClientResponse("x", unpriced))
    s = Setup(clients={"apify": client}, services={"apify": policy(("run_actor",))})

    with pytest.raises(GatewayDenied) as denied:
        s.gateway.call("apify", "run_actor", "x", run_id="run-1")

    assert denied.value.reason == "unknown_price"
    assert client.calls == []
    assert s.log.calls[0].status == "denied"


def test_latency_of_a_refused_call_is_zero() -> None:
    s = Setup(monthly_cap="0.69", took=timedelta(seconds=9))

    with pytest.raises(BudgetExceeded):
        s.gateway.call("anthropic", "complete", "x", run_id="run-1")

    assert s.log.calls[0].latency == timedelta(0)


def test_a_response_that_cannot_be_priced_is_booked_at_the_estimate() -> None:
    unpriced = Units("anthropic", "mystery_item", 1)
    client = FakeServiceClient(HAIKU_700K, lambda *_: ClientResponse("answer", unpriced))
    s = Setup(clients={"anthropic": client}, monthly_cap="1")

    response = s.gateway.call("anthropic", "complete", "x", run_id="run-1")

    assert response.cost == D("0.7")
    assert (s.log.calls[0].status, s.log.calls[0].error_kind) == ("ok", "unknown_price")
    with pytest.raises(BudgetExceeded):  # the reservation was settled, not leaked, and the 0.7 is booked
        s.gateway.call("anthropic", "complete", "x", run_id="run-2")
