import threading
from datetime import timedelta

import pytest

from app.gateway import BudgetExceeded, ClientResponse, FakeServiceClient, GatewayDenied
from tests.gateway.helpers import HAIKU_700K, PLACES_ONE, D, Setup, ok_client, policy


def test_the_rate_limit_denies_the_call_over_it_and_says_when_to_retry() -> None:
    s = Setup(services={"anthropic": policy(max_calls=2, per=timedelta(seconds=60))})

    s.gateway.call("anthropic", "complete", "x", run_id="run-1")
    s.clock.advance(timedelta(seconds=10))
    s.gateway.call("anthropic", "complete", "x", run_id="run-1")
    s.clock.advance(timedelta(seconds=5))
    with pytest.raises(GatewayDenied) as denied:
        s.gateway.call("anthropic", "complete", "x", run_id="run-1")

    assert denied.value.reason == "rate_limited"
    assert denied.value.retry_after == timedelta(seconds=45)  # the first call leaves the 60 s window at t=60
    assert len(s.clients["anthropic"].calls) == 2
    assert (s.log.calls[-1].status, s.log.calls[-1].error_kind) == ("denied", "rate_limited")


def test_the_rate_limit_frees_up_when_the_window_has_passed() -> None:
    s = Setup(services={"anthropic": policy(max_calls=1, per=timedelta(seconds=60))})
    s.gateway.call("anthropic", "complete", "x", run_id="run-1")

    s.clock.advance(timedelta(seconds=60))

    s.gateway.call("anthropic", "complete", "x", run_id="run-1")
    assert len(s.clients["anthropic"].calls) == 2


def test_a_call_over_the_rate_limit_does_not_reserve_budget_or_use_a_slot() -> None:
    s = Setup(services={"anthropic": policy(max_calls=1, per=timedelta(seconds=60))}, monthly_cap="0.7")
    s.gateway.call("anthropic", "complete", "x", run_id="run-1")

    for _ in range(3):  # three denials, none of them may take a slot or hold money
        with pytest.raises(GatewayDenied):
            s.gateway.call("anthropic", "complete", "x", run_id="run-1")

    s.clock.advance(timedelta(seconds=60))
    with pytest.raises(BudgetExceeded):  # now the rate limit lets it through and the cap is what stops it
        s.gateway.call("anthropic", "complete", "x", run_id="run-1")


def test_a_refused_budget_does_not_use_a_rate_limit_slot() -> None:
    s = Setup(services={"anthropic": policy(max_calls=2, per=timedelta(seconds=60))}, run_cap="1")
    s.gateway.call("anthropic", "complete", "x", run_id="run-1")  # slot 1, 0.7 of the run cap 1
    with pytest.raises(BudgetExceeded):
        s.gateway.call("anthropic", "complete", "x", run_id="run-1")  # refused: must not take slot 2

    s.gateway.call("anthropic", "complete", "x", run_id="run-2")  # slot 2 is still free


def test_limits_are_per_service() -> None:
    places = FakeServiceClient(PLACES_ONE, lambda *_: ClientResponse("place", PLACES_ONE))
    s = Setup(
        clients={"anthropic": ok_client(), "google_places": places},
        services={
            "anthropic": policy(max_calls=1, per=timedelta(seconds=60)),
            "google_places": policy(("details",), max_calls=1, per=timedelta(seconds=60)),
        },
    )

    s.gateway.call("anthropic", "complete", "x", run_id="run-1")
    s.gateway.call("google_places", "details", "pid", run_id="run-1")  # its own window


def test_the_concurrency_limit_denies_a_call_while_another_is_in_flight() -> None:
    entered, release = threading.Event(), threading.Event()

    def slow(_op: str, _req: object) -> ClientResponse:
        entered.set()
        assert release.wait(timeout=5)
        return ClientResponse("answer", HAIKU_700K)

    s = Setup(
        clients={"anthropic": FakeServiceClient(HAIKU_700K, slow)},
        services={"anthropic": policy(max_concurrent=1)},
    )
    first = threading.Thread(target=lambda: s.gateway.call("anthropic", "complete", "x", run_id="run-1"))
    first.start()
    assert entered.wait(timeout=5)

    with pytest.raises(GatewayDenied) as denied:
        s.gateway.call("anthropic", "complete", "x", run_id="run-2")
    release.set()
    first.join(timeout=5)

    assert denied.value.reason == "concurrency_limit"
    s.gateway.call("anthropic", "complete", "x", run_id="run-2")  # the slot is free again
    assert [c.status for c in s.log.calls] == ["denied", "ok", "ok"]


def test_concurrent_calls_never_overspend_the_monthly_cap() -> None:
    # Cap 2.2 USD fits three 0.7 USD calls. Eight threads ask at once; the three that are admitted are
    # still in flight while the other five ask, so reservations in flight must count.
    admitted = threading.Semaphore(0)
    release = threading.Event()

    def slow(_op: str, _req: object) -> ClientResponse:
        admitted.release()
        assert release.wait(timeout=5)
        return ClientResponse("answer", HAIKU_700K)

    client = FakeServiceClient(HAIKU_700K, slow)
    s = Setup(
        clients={"anthropic": client}, services={"anthropic": policy(max_concurrent=8)}, monthly_cap="2.2"
    )
    outcomes: list[str] = []
    done = threading.Semaphore(0)

    def ask(n: int) -> None:
        try:
            s.gateway.call("anthropic", "complete", "x", run_id=f"run-{n}")
            outcomes.append("ok")
        except BudgetExceeded:
            outcomes.append("exceeded")
        finally:
            done.release()

    threads = [threading.Thread(target=ask, args=(n,)) for n in range(8)]
    for t in threads:
        t.start()
    for _ in range(3):
        assert admitted.acquire(timeout=5)
    for _ in range(5):  # the five refused calls finish while the three admitted ones are in flight
        assert done.acquire(timeout=5)
    release.set()
    for t in threads:
        t.join(timeout=5)

    assert sorted(outcomes) == ["exceeded"] * 5 + ["ok"] * 3
    assert sum((c.cost for c in s.log.calls), D(0)) == D("2.1")


@pytest.mark.parametrize(
    "limits",
    [
        {"max_calls": 0},
        {"max_concurrent": 0},
        {"per": timedelta(0)},
    ],
)
def test_a_limit_must_be_positive(limits: dict[str, object]) -> None:
    with pytest.raises(ValueError, match="limits"):
        policy(**limits)  # type: ignore[arg-type]
