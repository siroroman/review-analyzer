from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.domain import RunStatus, Source
from app.pipeline import RunResult
from app.queue import FakeQueue
from app.storage import UnknownRun
from app.worker import NoAuthCheck, Outcome, Worker, create_worker_app
from tests.pipeline.helpers import World


def reviews_of(world: World) -> list[object]:
    return list(world.storage.reviews.list_for_place(Source.GOOGLE_MAPS, "g1"))


def test_a_queued_run_reaches_a_final_status_through_the_queue() -> None:
    world = World()
    queue = FakeQueue()
    run_id = world.new_run()
    queue.enqueue(run_id)

    handled = queue.deliver(Worker(world.pipeline).handle)

    assert handled == 1
    assert world.status(run_id) == RunStatus.DONE


def test_redelivery_of_a_finished_run_costs_nothing_and_adds_no_reviews() -> None:
    world = World()
    worker = Worker(world.pipeline)
    run_id = world.new_run()
    worker.handle(run_id)
    calls, scrapes = world.service_calls(), world.scrape_calls()
    reviews = len(reviews_of(world))
    cost = world.pipeline.run(run_id).cost
    assert calls > 0 and reviews > 0 and cost > Decimal(0)

    worker.handle(run_id)
    worker.handle(run_id)

    assert world.service_calls() == calls
    assert world.scrape_calls() == scrapes
    assert len(reviews_of(world)) == reviews
    assert world.pipeline.run(run_id).cost == cost


def test_redelivery_after_a_crash_resumes_without_paying_twice() -> None:
    world = World(failures={"classification": [RuntimeError("bug")]})
    worker = Worker(world.pipeline)
    run_id = world.new_run()
    with pytest.raises(RuntimeError):
        worker.handle(run_id)
    scrapes = world.scrape_calls()
    reviews = len(reviews_of(world))
    assert world.status(run_id) == RunStatus.CLASSIFYING

    worker.handle(run_id)

    assert world.status(run_id) == RunStatus.DONE
    assert world.scrape_calls() == scrapes
    assert len(reviews_of(world)) == reviews


def test_an_unknown_run_is_dropped_not_retried() -> None:
    assert Worker(World().pipeline).handle("999") == Outcome.UNKNOWN_RUN


def test_the_worker_only_calls_run() -> None:
    class Spy:
        def __init__(self) -> None:
            self.calls: list[str] = []

        def run(self, run_id: str) -> RunResult:
            self.calls.append(run_id)
            raise UnknownRun(run_id)

    spy = Spy()
    Worker(spy).handle("7")
    assert spy.calls == ["7"]


def test_the_endpoint_answers_200_for_done_and_unknown_and_500_for_a_bug() -> None:
    world = World(failures={"classification": [RuntimeError("bug")]})
    client = TestClient(
        create_worker_app(Worker(world.pipeline), auth=NoAuthCheck()), raise_server_exceptions=False
    )
    run_id = world.new_run()

    assert client.post("/tasks/run", json={"run_id": "999"}).status_code == 200
    assert client.post("/tasks/run", json={"run_id": run_id}).status_code == 500
    assert client.post("/tasks/run", json={"run_id": run_id}).status_code == 200
    assert world.status(run_id) == RunStatus.DONE
