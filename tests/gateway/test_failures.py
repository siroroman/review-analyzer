from datetime import timedelta

import pytest

from app.gateway import BudgetExceeded, ClientError, ClientTimeout, Tokens
from tests.gateway.helpers import D, Setup

CHARGED = Tokens("anthropic", "claude-haiku", 100_000, 0)  # 0.1 USD already charged by the provider


def test_a_timeout_is_logged_as_failed_with_no_cost_and_raised() -> None:
    s = Setup(fail_with=ClientTimeout())

    with pytest.raises(ClientTimeout):
        s.gateway.call("anthropic", "complete", "x", run_id="run-1")

    [call] = s.log.calls
    assert (call.status, call.error_kind, call.cost) == ("failed", "timeout", D(0))


def test_the_latency_of_a_failed_call_is_logged() -> None:
    s = Setup(fail_with=ClientTimeout(), took=timedelta(seconds=30))

    with pytest.raises(ClientTimeout):
        s.gateway.call("anthropic", "complete", "x", run_id="run-1")

    assert s.log.calls[0].latency == timedelta(seconds=30)


def test_a_failed_call_books_the_cost_that_was_actually_charged() -> None:
    s = Setup(fail_with=ClientError("overloaded", usage=CHARGED), run_cap="0.7")

    with pytest.raises(ClientError):
        s.gateway.call("anthropic", "complete", "x", run_id="run-1")

    [call] = s.log.calls
    assert (call.status, call.error_kind, call.cost) == ("failed", "overloaded", D("0.1"))
    assert (call.unit, call.units) == ("token", 100_000)
    # 0.1 of the 0.7 run cap is gone, so the next 0.7 estimate of that run no longer fits
    with pytest.raises(BudgetExceeded):
        s.gateway.call("anthropic", "complete", "x", run_id="run-1")


def test_an_unexpected_exception_is_logged_as_an_error_without_its_message_and_raised() -> None:
    s = Setup(fail_with=RuntimeError("boom with review text"))

    with pytest.raises(RuntimeError):
        s.gateway.call("anthropic", "complete", "x", run_id="run-1")

    [call] = s.log.calls
    assert (call.status, call.error_kind, call.cost) == ("failed", "error", D(0))
    assert "boom" not in repr(call)


def test_a_failed_call_releases_its_reservation() -> None:
    # monthly cap 0.7 fits exactly one 0.7 estimate; a leaked reservation would block every later call
    s = Setup(fail_with=ClientTimeout(), monthly_cap="0.7")

    for _ in range(3):
        with pytest.raises(ClientTimeout):
            s.gateway.call("anthropic", "complete", "x", run_id="run-1")

    assert [c.status for c in s.log.calls] == ["failed", "failed", "failed"]
