import pytest

from app.gateway import ClientError, ClientResponse, FakeServiceClient, GatewayDenied, Units
from tests.gateway.helpers import D, Setup, policy

FREE = Units("yasogan", "review", 3)
OPERATION = "scrape_google_reviews"


def free_setup(fail_with: Exception | None = None, max_calls: int = 100) -> Setup:
    def respond(_op: str, _req: object) -> ClientResponse:
        if fail_with is not None:
            raise fail_with
        return ClientResponse("answer", FREE)

    return Setup(
        clients={"yasogan": FakeServiceClient(FREE, respond)},
        services={"yasogan": policy((OPERATION,), max_calls=max_calls)},
    )


def test_a_service_that_costs_nothing_is_called_and_logged_at_zero() -> None:
    s = free_setup()
    response = s.gateway.call("yasogan", OPERATION, "x", run_id="run-1")
    assert response.cost == D(0)
    [call] = s.log.calls
    assert (call.status, call.cost, call.unit, call.units) == ("ok", D(0), "review", 3)


def test_a_free_call_still_obeys_the_traffic_limits() -> None:
    s = free_setup(max_calls=1)
    s.gateway.call("yasogan", OPERATION, "x", run_id="run-1")
    with pytest.raises(GatewayDenied) as denied:
        s.gateway.call("yasogan", OPERATION, "x", run_id="run-1")
    assert denied.value.reason == "rate_limited"


def test_a_failed_free_call_is_logged_and_the_error_passes_through() -> None:
    s = free_setup(fail_with=ClientError("schema_changed"))
    with pytest.raises(ClientError, match="schema_changed"):
        s.gateway.call("yasogan", OPERATION, "x", run_id="run-1")
    assert [(c.status, c.error_kind, c.cost) for c in s.log.calls] == [("failed", "schema_changed", D(0))]
