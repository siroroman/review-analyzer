import threading
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient

from app.api import create_app
from app.domain import RunStatus
from app.queue import LocalQueue, Queue, QueueError
from app.worker import Worker
from tests.api.helpers import HEADERS, config
from tests.pipeline.helpers import World
from tests.places.helpers import Setup


class Handler:
    """A handler that remembers each Run id it got and fails the first `failures` times."""

    def __init__(self, failures: int = 0) -> None:
        self.handled: list[str] = []
        self.failures = failures

    def __call__(self, run_id: str) -> None:
        self.handled.append(run_id)
        if self.failures:
            self.failures -= 1
            raise RuntimeError("bug")


def make(handler: Handler, *, max_attempts: int = 3) -> tuple[LocalQueue, list[timedelta]]:
    delays: list[timedelta] = []
    return LocalQueue(handler, delays.append, max_attempts=max_attempts), delays


def test_it_is_a_queue_and_hands_an_enqueued_run_to_the_handler_in_the_background() -> None:
    handler = Handler()
    queue, _ = make(handler)
    port: Queue = queue

    port.enqueue("1")
    port.enqueue("2")
    queue.join()

    assert handler.handled == ["1", "2"]


def test_the_handler_runs_on_another_thread() -> None:
    seen: list[int] = []
    queue = LocalQueue(lambda _: seen.append(threading.get_ident()), lambda _: None)
    queue.enqueue("1")
    queue.join()
    assert seen and seen[0] != threading.get_ident()


def test_a_failed_run_is_tried_again_after_a_delay_until_it_goes_through() -> None:
    handler = Handler(failures=2)
    queue, delays = make(handler)

    queue.enqueue("1")
    queue.join()

    assert handler.handled == ["1", "1", "1"]
    assert len(delays) == 2


def test_a_run_that_keeps_failing_is_given_up_after_max_attempts_and_the_queue_goes_on() -> None:
    handler = Handler(failures=99)
    queue, _ = make(handler, max_attempts=2)

    queue.enqueue("1")
    queue.join()
    handler.failures = 0
    queue.enqueue("2")
    queue.join()

    assert handler.handled == ["1", "1", "2"]


def test_a_repeat_of_a_message_that_is_still_waiting_changes_nothing() -> None:
    release, started = threading.Event(), threading.Event()
    handled: list[str] = []

    def slow(run_id: str) -> None:
        handled.append(run_id)
        started.set()
        release.wait(timeout=5)

    queue = LocalQueue(slow, lambda _: None)
    queue.enqueue("1")
    assert started.wait(timeout=5)
    queue.enqueue("1")
    queue.enqueue("1")
    release.set()
    queue.join()

    assert handled == ["1"]


def test_a_run_id_that_cannot_be_a_message_is_refused() -> None:
    queue, _ = make(Handler())
    with pytest.raises(QueueError):
        queue.enqueue("")


def test_a_run_goes_through_the_worker_and_a_repeat_after_it_costs_nothing() -> None:
    world = World()
    queue = LocalQueue(Worker(world.pipeline).handle, lambda _: None)
    run_id = world.new_run()

    queue.enqueue(run_id)
    queue.join()
    assert world.status(run_id) == RunStatus.DONE
    calls, scrapes = world.service_calls(), world.scrape_calls()

    queue.enqueue(run_id)
    queue.join()

    assert world.service_calls() == calls
    assert world.scrape_calls() == scrapes


def test_the_status_of_a_run_through_the_local_queue_ends_with_the_final_counts() -> None:
    world = World()
    queue = LocalQueue(Worker(world.pipeline).handle, lambda _: None)
    api = TestClient(
        create_app(
            storage=world.storage,
            places=Setup().places,
            queue=queue,
            pipeline=world.pipeline,
            clock=world.clock,
            config=config(),
        )
    )
    run_id = world.new_run()
    queued = api.get(f"/runs/{run_id}", headers=HEADERS).json()
    assert (queued["downloaded"], queued["classified"]) == (None, None)

    queue.enqueue(run_id)
    queue.join()

    done = api.get(f"/runs/{run_id}", headers=HEADERS).json()
    assert (done["status"], done["finished"], done["budget"]) == ("done", True, "5")
    assert done["downloaded"] == {"google_maps": 40}
    assert (done["classified"], done["to_classify"]) == (done["to_classify"], 40 - done["flagged"])
    steps = done["step_cost"]
    assert sum(float(steps[k]) for k in ("downloading", "classifying", "analysis")) == float(done["cost"])
