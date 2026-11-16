import base64
import json
from datetime import timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.domain import FakeClock
from app.main import (
    SECRET_VARIABLES,
    SETTING_VARIABLES,
    MetadataToken,
    SystemClock,
    ThreadSleeper,
    build_apps,
)
from app.queue import QueueError
from app.storage import in_memory_storage
from app.transport import FakeTransport, HttpError, HttpResponse, MissingSecret
from tests.main.helpers import ACCESS_TOKEN, ENVIRON, PLACE_ID, Internet, clock

DEMO = {"Authorization": "Bearer demo-token-1"}


def apps(internet: Internet, environ: dict[str, str] | None = None) -> tuple[TestClient, TestClient]:
    wall = clock()
    built = build_apps(environ or ENVIRON, transport=internet, storage=in_memory_storage(wall), clock=wall)
    return TestClient(built.api), TestClient(built.worker)


def test_search_start_a_run_the_worker_runs_it_and_the_result_shows() -> None:
    internet = Internet()
    api, worker = apps(internet)

    found = api.get("/places/suggest", params={"q": "Globus"}, headers=DEMO)
    assert found.status_code == 200
    assert found.json()[0]["place_id"] == PLACE_ID

    started = api.post(
        "/runs", json={"place_ids": [PLACE_ID], "name": "Globus", "industry": "retail"}, headers=DEMO
    )
    assert started.status_code == 202
    run_id = started.json()["run_id"]

    assert len(internet.tasks) == 1  # the Run went to the queue, not to the pipeline
    message = base64.b64decode(internet.tasks[0]["httpRequest"]["body"])  # type: ignore[index]
    assert json.loads(message) == {"run_id": run_id}

    handled = worker.post("/tasks/run", json={"run_id": run_id})
    assert handled.json() == {"outcome": "handled"}

    result = api.get(f"/runs/{run_id}/result", headers=DEMO)
    assert result.status_code == 200
    assert result.json()["status"] == "done"
    assert result.json()["reviews"] == 40
    assert result.json()["insights"][0]["text"] == "Hosté chválí obsluhu."


def test_only_the_real_services_are_called_and_the_task_carries_the_service_account_token() -> None:
    internet = Internet()
    api, _ = apps(internet)
    api.post("/runs", json={"place_ids": [PLACE_ID], "name": "Globus", "industry": "retail"}, headers=DEMO)
    assert internet.hosts() == {
        "places.googleapis.com",
        "cloudtasks.googleapis.com",
        "metadata.google.internal",
    }
    task_request = next(r for r in internet.requests if "cloudtasks" in r.url)
    assert task_request.headers["Authorization"] == f"Bearer {ACCESS_TOKEN}"


def test_the_other_source_is_unavailable_but_a_search_and_a_run_work_without_it() -> None:
    api, _ = apps(Internet())
    started = api.post(
        "/runs", json={"place_ids": [PLACE_ID], "name": "Globus", "industry": "retail"}, headers=DEMO
    )
    assert started.status_code == 202


@pytest.mark.parametrize("name", [key for key in ENVIRON if key not in {"ADMIN_TOKEN", "LANGFUSE_HOST"}])
@pytest.mark.parametrize("value", [None, "", "   "])
def test_a_missing_or_empty_secret_fails_at_start_and_names_only_the_variable(
    name: str, value: str | None
) -> None:
    environ = {key: val for key, val in ENVIRON.items() if key != name}
    if value is not None:
        environ[name] = value
    wall = clock()
    with pytest.raises(MissingSecret) as raised:
        build_apps(environ, transport=Internet(), storage=in_memory_storage(wall), clock=wall)
    assert name in str(raised.value)
    assert not any(secret in str(raised.value) for secret in ENVIRON.values())


def test_the_real_clock_gives_an_aware_time_and_the_real_sleeper_returns() -> None:
    assert SystemClock().now().tzinfo is not None
    ThreadSleeper().sleep(timedelta(0))


def _token(*steps: HttpResponse | HttpError) -> tuple[MetadataToken, FakeTransport, FakeClock]:
    wall, transport = clock(), FakeTransport(*steps)
    return MetadataToken(transport, wall), transport, wall


def _granted(access: str = "t1", expires_in: int = 3600) -> HttpResponse:
    return HttpResponse(200, json.dumps({"access_token": access, "expires_in": expires_in}).encode())


def test_the_token_is_read_once_and_asked_again_a_minute_before_it_expires() -> None:
    token, transport, wall = _token(_granted("t1"), _granted("t2"))
    assert token().get_secret_value() == "t1"
    assert token().get_secret_value() == "t1"
    assert len(transport.requests) == 1
    assert transport.requests[0].headers == {"Metadata-Flavor": "Google"}
    wall.advance(timedelta(seconds=3541))
    assert token().get_secret_value() == "t2"


@pytest.mark.parametrize(
    "step",
    [HttpError("down"), HttpResponse(403, b"{}"), HttpResponse(200, b"not json"), HttpResponse(200, b"{}")],
)
def test_no_token_from_the_metadata_server_is_a_queue_error_without_its_body(
    step: HttpResponse | HttpError,
) -> None:
    token, _, _ = _token(step)
    with pytest.raises(QueueError):
        token()


def test_env_example_lists_every_variable_with_a_placeholder() -> None:
    lines = (Path(__file__).parents[2] / ".env.example").read_text().splitlines()
    listed = dict(line.split("=", 1) for line in lines if line and not line.startswith("#"))
    assert set(listed) == set(SECRET_VARIABLES) | set(SETTING_VARIABLES)
    keys = [name for name in SECRET_VARIABLES if name.endswith("_KEY") or name.endswith("_TOKEN")]
    assert all(listed[name].startswith("your-") for name in keys)
