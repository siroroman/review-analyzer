from datetime import timedelta

import pytest

from app.gateway import ClientResponse, FakeServiceClient, GatewayDenied
from tests.gateway.helpers import HAIKU_700K, PLACES_ONE, START, D, Setup, ok_client, policy


def test_an_allowed_call_returns_the_answer_with_usage_and_cost() -> None:
    s = Setup()

    response = s.gateway.call("anthropic", "complete", {"prompt": "hi"}, run_id="run-1")

    assert response.payload == "answer"
    assert response.usage == HAIKU_700K
    assert response.cost == D("0.7")
    assert s.clients["anthropic"].calls == [("complete", {"prompt": "hi"})]


def test_an_allowed_call_is_logged_once_with_its_facts() -> None:
    s = Setup(took=timedelta(seconds=2))

    s.gateway.call("anthropic", "complete", "x", run_id="run-7")

    [call] = s.log.calls
    assert (call.service, call.operation, call.run_id, call.status) == (
        "anthropic",
        "complete",
        "run-7",
        "ok",
    )
    assert call.cost == D("0.7")
    assert (call.unit, call.units) == ("token", 300_000)
    assert call.latency == timedelta(seconds=2)
    assert call.error_kind is None
    assert call.at == START + timedelta(seconds=2)


def test_units_of_a_per_item_service_are_logged_with_their_unit() -> None:
    clients = {"google_places": FakeServiceClient(PLACES_ONE, lambda *_: ClientResponse("place", PLACES_ONE))}
    s = Setup(clients=clients, services={"google_places": policy(("details",))})

    s.gateway.call("google_places", "details", "pid", run_id="r")

    [call] = s.log.calls
    assert (call.unit, call.units, call.cost) == ("details_request", 1, D("0.017"))


@pytest.mark.parametrize(
    ("service", "operation", "reason"),
    [
        ("openrouter", "complete", "service_not_allowed"),
        ("anthropic", "delete_everything", "operation_not_allowed"),
    ],
)
def test_a_service_or_operation_off_the_allow_list_is_denied_and_logged(
    service: str, operation: str, reason: str
) -> None:
    s = Setup(clients={"anthropic": ok_client(), "openrouter": ok_client()})

    with pytest.raises(GatewayDenied) as denied:
        s.gateway.call(service, operation, "x", run_id="run-1")

    assert denied.value.reason == reason
    assert s.clients["anthropic"].calls == []
    assert s.clients["openrouter"].calls == []
    [call] = s.log.calls
    assert (call.service, call.operation, call.status, call.error_kind) == (
        service,
        operation,
        "denied",
        reason,
    )
    assert call.cost == D(0)


def test_a_service_without_a_client_is_a_configuration_error() -> None:
    with pytest.raises(ValueError, match="openrouter"):
        Setup(clients={"anthropic": ok_client()}, services={"openrouter": policy()})


def test_the_call_log_never_holds_a_request_or_a_response() -> None:
    review_in_request = "REQUEST-TEXT-reviewer-Jan-Novak"
    review_in_response = "RESPONSE-TEXT-phone-777123456"
    s = Setup(clients={"anthropic": ok_client(payload=review_in_response)})

    s.gateway.call("anthropic", "complete", review_in_request, run_id="run-1")
    with pytest.raises(GatewayDenied):
        s.gateway.call("anthropic", "other", review_in_request, run_id="run-1")

    assert len(s.log.calls) == 2
    for call in s.log.calls:
        assert review_in_request not in repr(call)
        assert review_in_response not in repr(call)
        assert set(vars(call)) == {
            "service",
            "operation",
            "run_id",
            "status",
            "cost",
            "unit",
            "units",
            "latency",
            "error_kind",
            "at",
        }
