from datetime import timedelta

import pytest

from app.gateway import BudgetExceeded, ClientError, ClientTimeout, GatewayDenied
from app.llm import ModelRef, Route
from tests.llm.helpers import (
    HAIKU,
    HAIKU_USAGE,
    JEV,
    JEV_USAGE,
    VALID,
    Answer,
    Setup,
    requests,
    scripted,
)

SECOND = timedelta(seconds=1)
SERVER_ERROR = ClientError("server_error")


def test_a_timeout_is_retried_after_a_backoff() -> None:
    s = Setup(jev=lambda c: scripted(JEV_USAGE, ClientTimeout(), VALID, clock=c))

    result = s.llm.complete("classify", "Rate this.", Answer, run_id="run-1")

    assert result == Answer(label="service", score=3)
    assert s.sleeper.delays == [SECOND]
    assert len(s.openrouter.calls) == 2
    assert s.anthropic.calls == []


def test_a_5xx_is_retried_and_the_backoff_doubles() -> None:
    s = Setup(jev=lambda c: scripted(JEV_USAGE, SERVER_ERROR, SERVER_ERROR, VALID, clock=c))

    s.llm.complete("classify", "Rate this.", Answer, run_id="run-1")

    assert s.sleeper.delays == [SECOND, 2 * SECOND]
    assert len(s.openrouter.calls) == 3


def test_the_fallback_model_is_used_after_the_retries_are_spent() -> None:
    s = Setup(jev=lambda c: scripted(JEV_USAGE, ClientTimeout(), ClientTimeout(), ClientTimeout(), clock=c))

    result = s.llm.complete("classify", "Rate this.", Answer, run_id="run-1")

    assert result == Answer(label="service", score=3)
    assert len(s.openrouter.calls) == 3  # one call and two retries
    assert [r.model for r in requests(s.anthropic)] == ["claude-haiku"]


def test_a_failure_that_is_not_worth_repeating_goes_straight_to_the_fallback() -> None:
    s = Setup(jev=lambda c: scripted(JEV_USAGE, ClientError("bad_request"), clock=c))

    s.llm.complete("classify", "Rate this.", Answer, run_id="run-1")

    assert len(s.openrouter.calls) == 1
    assert s.sleeper.delays == []
    assert len(s.anthropic.calls) == 1


def test_the_fallback_gets_its_own_retries() -> None:
    s = Setup(
        jev=lambda c: scripted(JEV_USAGE, ClientError("bad_request"), clock=c),
        haiku=lambda c: scripted(HAIKU_USAGE, SERVER_ERROR, VALID, clock=c),
    )

    s.llm.complete("classify", "Rate this.", Answer, run_id="run-1")

    assert len(s.anthropic.calls) == 2


def test_when_the_fallback_fails_too_the_last_error_is_raised() -> None:
    s = Setup(
        jev=lambda c: scripted(JEV_USAGE, ClientError("bad_request"), clock=c),
        haiku=lambda c: scripted(HAIKU_USAGE, ClientError("overloaded"), clock=c),
    )

    with pytest.raises(ClientError) as failure:
        s.llm.complete("classify", "Rate this.", Answer, run_id="run-1")

    assert failure.value.kind == "overloaded"


def test_a_route_without_a_fallback_raises_after_its_retries() -> None:
    s = Setup(
        jev=lambda c: scripted(JEV_USAGE, ClientTimeout(), ClientTimeout(), ClientTimeout(), clock=c),
        routes={"classify": Route(JEV)},
    )

    with pytest.raises(ClientTimeout):
        s.llm.complete("classify", "Rate this.", Answer, run_id="run-1")

    assert len(s.openrouter.calls) == 3


def test_no_retries_when_configured_so() -> None:
    s = Setup(jev=lambda c: scripted(JEV_USAGE, ClientTimeout(), clock=c), max_retries=0)

    s.llm.complete("classify", "Rate this.", Answer, run_id="run-1")

    assert len(s.openrouter.calls) == 1
    assert s.sleeper.delays == []
    assert len(s.anthropic.calls) == 1


def test_an_exceeded_budget_is_not_retried_and_does_not_fall_back() -> None:
    s = Setup(run_cap="0.1", routes={"classify": Route(HAIKU, JEV)})  # a haiku call is estimated at 0.2

    with pytest.raises(BudgetExceeded):
        s.llm.complete("classify", "Rate this.", Answer, run_id="run-1")

    assert s.anthropic.calls == []
    assert s.openrouter.calls == []
    assert s.sleeper.delays == []


def test_a_denied_call_is_not_retried_and_does_not_fall_back() -> None:
    s = Setup(routes={"classify": Route(ModelRef("mistral", "large"), JEV)})

    with pytest.raises(GatewayDenied):
        s.llm.complete("classify", "Rate this.", Answer, run_id="run-1")

    assert s.openrouter.calls == []
    assert s.sleeper.delays == []
