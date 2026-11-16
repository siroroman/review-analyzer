from datetime import timedelta

from app.domain import RunStatus
from app.gateway import ClientError, Suggestion
from tests.api.helpers import HEADERS, Api, cafe

RUN = {"place_ids": ["g1"], "name": "Kavárna", "industry": "cafe"}


def test_a_new_run_is_queued_and_enqueued() -> None:
    api = Api(known=[cafe()])
    response = api.client.post("/runs", json=RUN, headers=HEADERS)
    body = response.json()
    assert (response.status_code, body["status"], body["reused"]) == (202, "queued", False)
    assert api.queue.enqueued == [body["run_id"]]


def test_a_fresh_run_of_the_same_company_is_returned_instead_of_a_duplicate() -> None:
    api = Api(known=[cafe()])
    first = api.client.post("/runs", json=RUN, headers=HEADERS).json()
    _finish(api, first["run_id"])
    again = api.client.post("/runs", json={**RUN, "name": "Other name"}, headers=HEADERS)
    assert (again.status_code, again.json()) == (
        200,
        {"run_id": first["run_id"], "status": "done", "reused": True},
    )
    assert api.queue.enqueued == [first["run_id"]]


def test_a_stale_run_is_not_reused() -> None:
    api = Api(known=[cafe()])
    first = api.client.post("/runs", json=RUN, headers=HEADERS).json()
    _finish(api, first["run_id"])
    api.advance(timedelta(hours=25))
    second = api.client.post("/runs", json=RUN, headers=HEADERS).json()
    assert second["run_id"] != first["run_id"]


def test_an_unknown_place_is_422() -> None:
    api = Api()
    assert api.client.post("/runs", json=RUN, headers=HEADERS).status_code == 422
    assert api.queue.enqueued == []


def test_when_places_is_unavailable_the_answer_is_503() -> None:
    api = Api(known=[cafe()])
    api.setup.google.error = ClientError("unavailable")
    response = api.client.post("/runs", json=RUN, headers=HEADERS)
    assert response.status_code == 503
    assert api.queue.enqueued == []


def test_the_status_of_a_run() -> None:
    api = Api(known=[cafe()])
    run_id = api.client.post("/runs", json=RUN, headers=HEADERS).json()["run_id"]
    status = api.client.get(f"/runs/{run_id}", headers=HEADERS).json()
    assert {k: status[k] for k in ("run_id", "status", "finished", "cost")} == {
        "run_id": run_id,
        "status": "queued",
        "finished": False,
        "cost": "0",
    }
    _finish(api, run_id)
    assert api.client.get(f"/runs/{run_id}", headers=HEADERS).json()["finished"] is True


def test_an_unknown_run_is_404() -> None:
    api = Api()
    assert api.client.get("/runs/nope", headers=HEADERS).status_code == 404
    assert api.client.get("/runs/nope/result", headers=HEADERS).status_code == 404


def test_suggestions_come_from_places() -> None:
    api = Api()
    api.setup.google.suggestions["kav"] = (Suggestion("g1", "Kavárna, Praha"),)
    response = api.client.get("/places/suggest", params={"q": "kav"}, headers=HEADERS)
    assert response.json() == [{"place_id": "g1", "text": "Kavárna, Praha"}]


def _finish(api: Api, run_id: str) -> None:
    for status in (RunStatus.DOWNLOADING, RunStatus.CLASSIFYING, RunStatus.ANALYZING, RunStatus.DONE):
        api.storage.runs.advance(run_id, status)


def test_a_blank_name_is_422() -> None:
    api = Api(known=[cafe()])
    assert api.client.post("/runs", json={**RUN, "name": "   "}, headers=HEADERS).status_code == 422
    assert api.queue.enqueued == []
