import pytest

from tests.api.helpers import HEADERS, Api, cafe


@pytest.mark.parametrize("query", ["", "x" * 101, "kav<script>", "a;b", "kav\u0000"])
def test_a_bad_search_text_is_422(query: str) -> None:
    assert Api().client.get("/places/suggest", params={"q": query}, headers=HEADERS).status_code == 422


def test_czech_letters_and_punctuation_are_allowed() -> None:
    api = Api()
    response = api.client.get("/places/suggest", params={"q": "Kavárna U Čápa, Praha 1"}, headers=HEADERS)
    assert response.status_code == 200


@pytest.mark.parametrize(
    "body",
    [
        {"place_ids": []},
        {"place_ids": ["g1"] * 21},
        {"place_ids": ["g 1"]},
        {"place_ids": [""]},
        {"place_ids": ["g" * 301]},
        {},
    ],
)
def test_a_bad_run_request_is_422_and_makes_no_paid_call(body: dict[str, object]) -> None:
    api = Api(known=[cafe()])
    assert api.client.post("/runs", json=body, headers=HEADERS).status_code == 422
    assert api.setup.google.asked("details") == []
    assert api.queue.enqueued == []
