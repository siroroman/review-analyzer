import pytest
from fastapi.testclient import TestClient

from app.worker import (
    FakeTokenVerifier,
    NoAuthCheck,
    OidcCheck,
    Outcome,
    Worker,
    WorkerAuthConfigError,
    auth_from_env,
    create_worker_app,
)

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
    return client.post(
        "/tasks/run", json={"run_id": "1"}, headers={"Authorization": f"Bearer {token}"}
    ).status_code


def test_a_valid_token_of_the_queue_account_runs_the_handler() -> None:
    worker = RecordingWorker()
    client, verifier = make_client(worker)

    status = call(client, verifier.issue(email=ACCOUNT, audience=AUDIENCE))

    assert status == 200
    assert worker.handled == ["1"]


def test_a_token_for_another_audience_is_401() -> None:
    worker = RecordingWorker()
    client, verifier = make_client(worker)

    assert call(client, verifier.issue(email=ACCOUNT, audience="https://other.example")) == 401
    assert worker.handled == []


def test_a_token_of_another_account_is_401() -> None:
    worker = RecordingWorker()
    client, verifier = make_client(worker)

    assert call(client, verifier.issue(email="attacker@example.com", audience=AUDIENCE)) == 401
    assert call(client, verifier.issue(email=ACCOUNT, audience=AUDIENCE, email_verified=False)) == 401
    assert worker.handled == []


def test_an_expired_token_is_401() -> None:
    worker = RecordingWorker()
    client, verifier = make_client(worker)

    assert call(client, verifier.issue(email=ACCOUNT, audience=AUDIENCE, expired=True)) == 401
    assert worker.handled == []


def test_a_token_nobody_issued_is_401() -> None:
    worker = RecordingWorker()
    client, _ = make_client(worker)

    assert call(client, "forged") == 401
    assert worker.handled == []


def test_no_auth_check_lets_a_call_without_a_token_through() -> None:
    worker = RecordingWorker()
    client = TestClient(create_worker_app(worker, auth=NoAuthCheck()))

    assert client.post("/tasks/run", json={"run_id": "1"}).status_code == 200
    assert worker.handled == ["1"]


def test_config_with_audience_and_account_checks_tokens() -> None:
    verifier = FakeTokenVerifier()
    env = {"WORKER_OIDC_AUDIENCE": AUDIENCE, "WORKER_OIDC_SERVICE_ACCOUNT": ACCOUNT}

    auth = auth_from_env(env, verifier)

    assert auth.allows(f"Bearer {verifier.issue(email=ACCOUNT, audience=AUDIENCE)}")
    assert not auth.allows(None)


def test_config_without_audience_or_account_fails_instead_of_skipping_the_check() -> None:
    for env in ({}, {"WORKER_OIDC_AUDIENCE": AUDIENCE}, {"WORKER_OIDC_SERVICE_ACCOUNT": ACCOUNT}):
        with pytest.raises(WorkerAuthConfigError):
            auth_from_env(env, FakeTokenVerifier())


def test_the_check_is_off_only_with_an_explicit_true_flag() -> None:
    assert isinstance(auth_from_env({"WORKER_AUTH_DISABLED": "true"}, FakeTokenVerifier()), NoAuthCheck)
    for flag in ("false", "1", "yes", ""):
        with pytest.raises(WorkerAuthConfigError):
            auth_from_env({"WORKER_AUTH_DISABLED": flag}, FakeTokenVerifier())
