import base64

import pytest
from pydantic import SecretStr

from app.queue import CloudTasksConfig, CloudTasksQueue, QueueError
from app.transport import FakeTransport, HttpError, HttpResponse, HttpTimeout
from tests.adapters.helpers import body_of, fixture

BEARER = "ya29.token-secret-123"
CONFIG = CloudTasksConfig(
    project="review-analyzer",
    location="europe-west1",
    queue="runs",
    worker_url="https://worker.example/tasks/run",
    service_account="worker@review-analyzer.iam.example",
)


def queue(*steps: HttpResponse | HttpError) -> tuple[CloudTasksQueue, FakeTransport]:
    transport = FakeTransport(*steps)
    return CloudTasksQueue(CONFIG, transport, lambda: SecretStr(BEARER)), transport


def test_creates_one_named_task_that_posts_the_run_id_to_the_worker() -> None:
    cloud, transport = queue(fixture("cloud_tasks_create_ok.json"))
    cloud.enqueue("42")

    sent = transport.requests[0]
    assert sent.method == "POST"
    assert sent.url == (
        "https://cloudtasks.googleapis.com/v2/projects/review-analyzer/locations/europe-west1"
        "/queues/runs/tasks"
    )
    assert sent.headers["Authorization"] == f"Bearer {BEARER}"
    task = body_of(sent.body)["task"]
    assert isinstance(task, dict)
    assert task["name"] == "projects/review-analyzer/locations/europe-west1/queues/runs/tasks/run-42"
    http = task["httpRequest"]
    assert http["url"] == "https://worker.example/tasks/run"
    assert http["httpMethod"] == "POST"
    assert http["oidcToken"] == {"serviceAccountEmail": "worker@review-analyzer.iam.example"}
    assert base64.b64decode(http["body"]) == b'{"run_id": "42"}'


def test_a_duplicate_enqueue_is_accepted_because_the_task_already_exists() -> None:
    cloud, _ = queue(fixture("cloud_tasks_already_exists.json", 409))
    cloud.enqueue("42")


def test_a_refusal_raises_without_the_token_or_the_body_in_the_message() -> None:
    cloud, _ = queue(fixture("cloud_tasks_permission_denied.json", 403))
    with pytest.raises(QueueError) as caught:
        cloud.enqueue("42")
    assert "403" in str(caught.value)
    assert BEARER not in str(caught.value)
    assert "IAM" not in str(caught.value)


@pytest.mark.parametrize("failure", [HttpError("no answer"), HttpTimeout("slow")])
def test_no_answer_raises_queue_error(failure: HttpError) -> None:
    cloud, _ = queue(failure)
    with pytest.raises(QueueError):
        cloud.enqueue("42")


def test_a_run_id_that_cannot_be_a_task_name_is_refused_before_any_call() -> None:
    cloud, transport = queue()
    with pytest.raises(QueueError):
        cloud.enqueue("../42")
    assert transport.requests == []
