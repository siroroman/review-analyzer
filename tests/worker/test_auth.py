from fastapi.testclient import TestClient

from app.queue import FakeQueue
from app.worker import FakeTokenVerifier, OidcCheck, Outcome, Worker, create_worker_app

AUDIENCE = "https://worker.example.run.app"
ACCOUNT = "queue@project.iam.gserviceaccount.com"


class RecordingWorker(Worker):
    def __init__(self) -> None:
        self.handled: list[str] = []

    def handle(self, run_id: str) -> Outcome:
        self.handled.append(run_id)
        return Outcome.HANDLED


def make_client(worker: Worker) -> tuple[TestClient, FakeTokenVerifier]:
    verifier = FakeTokenVerifier()
    auth = OidcCheck(verifier=verifier, audience=AUDIENCE, service_account_email=ACCOUNT)
    return TestClient(create_worker_app(worker, auth=auth)), verifier


def test_a_call_without_a_token_is_401_and_the_handler_does_not_run() -> None:
    worker = RecordingWorker()
    client, _ = make_client(worker)

    response = client.post("/tasks/run", json={"run_id": "1"})

    assert response.status_code == 401
    assert worker.handled == []


def call(client: TestClient, token: str) -> int:
    return client.post("/tasks/run", json={"run_id": "1"}, headers={"Authorization": f"Bearer {token}"}).status_code


def test_a_valid_token_of_the_queue_account_runs_the_handler() -> None:
    worker = RecordingWorker()
    client, verifier = make_client(worker)

    status = call(client, verifier.issue(email=ACCOUNT, audience=AUDIENCE))

    assert status == 200
    assert worker.handled == ["1"]
