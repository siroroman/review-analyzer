from app.gateway import ClientError
from tests.api.helpers import HEADERS, Api, cafe
from tests.places.helpers import google, pages
from tests.storage.helpers import call

RUN = {"place_ids": ["g1"], "name": "Kavárna", "industry": "cafe"}


def test_branches_are_candidates_found_by_the_name_of_the_place() -> None:
    api = Api(known=[cafe()])
    api.setup.google.pages = pages([google("g2", "Kavárna", "Brno"), google("g3", "Kavárna Plus", "Plzeň")])
    response = api.client.get("/places/g1/branches", headers=HEADERS)
    assert response.json() == [
        {"place_id": "g2", "name": "Kavárna", "address": "Brno"},
        {"place_id": "g3", "name": "Kavárna Plus", "address": "Plzeň"},
    ]


def test_a_place_without_branches_has_an_empty_list() -> None:
    api = Api(known=[cafe()])
    assert api.client.get("/places/g1/branches", headers=HEADERS).json() == []


def test_branches_of_an_unknown_place_are_404() -> None:
    api = Api()
    assert api.client.get("/places/nope/branches", headers=HEADERS).status_code == 404


def test_branches_when_places_is_unavailable_are_503() -> None:
    api = Api(known=[cafe()])
    api.setup.google.error = ClientError("unavailable")
    assert api.client.get("/places/g1/branches", headers=HEADERS).status_code == 503


def test_branches_need_a_demo_token() -> None:
    api = Api(known=[cafe()])
    assert api.client.get("/places/g1/branches").status_code == 401


def test_a_place_id_with_odd_characters_is_422() -> None:
    api = Api()
    assert api.client.get("/places/a%20b/branches", headers=HEADERS).status_code == 422


def test_the_status_carries_the_cost_of_the_runs_service_calls() -> None:
    api = Api(known=[cafe()])
    run_id = api.client.post("/runs", json=RUN, headers=HEADERS).json()["run_id"]
    assert api.client.get(f"/runs/{run_id}", headers=HEADERS).json()["cost"] == "0"
    api.storage.calls.record(call(run_id=run_id, cost="0.25"))
    api.storage.calls.record(call(run_id=run_id, cost="0.5"))
    api.storage.calls.record(call(run_id="other", cost="9"))
    assert api.client.get(f"/runs/{run_id}", headers=HEADERS).json()["cost"] == "0.75"
