from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta

from tests.api.helpers import HEADERS, OTHER_DEMO, Api, cafe

RUN = {"place_ids": ["g1"], "name": "Kavárna", "industry": "cafe"}


def _suggest(api: Api, headers: dict[str, str] | None = None) -> int:
    response = api.client.get("/places/suggest", params={"q": "kav"}, headers=headers or HEADERS)
    return int(response.status_code)


def test_the_third_request_in_a_minute_is_429_with_retry_after() -> None:
    api = Api(requests_per_minute=2)
    assert [_suggest(api), _suggest(api)] == [200, 200]
    response = api.client.get("/places/suggest", params={"q": "kav"}, headers=HEADERS)
    assert response.status_code == 429
    assert int(response.headers["Retry-After"]) >= 1


def test_the_window_moves_with_the_clock() -> None:
    api = Api(requests_per_minute=1)
    assert _suggest(api) == 200
    assert _suggest(api) == 429
    api.advance(timedelta(seconds=61))
    assert _suggest(api) == 200


def test_requests_without_a_token_count_too() -> None:
    api = Api(requests_per_minute=1)
    assert api.client.get("/places/suggest", params={"q": "kav"}).status_code == 401
    assert api.client.get("/places/suggest", params={"q": "kav"}).status_code == 429


def test_the_openapi_description_is_not_rate_limited() -> None:
    api = Api(requests_per_minute=1)
    assert [api.client.get("/openapi.json").status_code for _ in range(3)] == [200, 200, 200]


def test_the_daily_limit_of_runs_is_per_token() -> None:
    api = Api(known=[cafe("g1"), cafe("g2")], runs_per_day=1)
    first = api.client.post("/runs", json=RUN, headers=HEADERS)
    second = api.client.post("/runs", json={**RUN, "place_ids": ["g2"]}, headers=HEADERS)
    other = api.client.post(
        "/runs", json={**RUN, "place_ids": ["g2"]}, headers={"Authorization": f"Bearer {OTHER_DEMO}"}
    )
    assert (first.status_code, second.status_code, other.status_code) == (202, 429, 202)


def test_a_denied_run_calls_nothing_paid_and_creates_nothing() -> None:
    api = Api(known=[cafe("g1"), cafe("g2")], runs_per_day=1)
    api.client.post("/runs", json=RUN, headers=HEADERS)
    asked = len(api.setup.google.asked("details"))
    api.client.post("/runs", json={**RUN, "place_ids": ["g2"]}, headers=HEADERS)
    assert len(api.setup.google.asked("details")) == asked
    assert len(api.queue.enqueued) == 1


def test_the_daily_limit_resets_on_the_next_utc_day() -> None:
    api = Api(known=[cafe("g1"), cafe("g2")], runs_per_day=1)
    api.client.post("/runs", json=RUN, headers=HEADERS)
    assert api.client.post("/runs", json={**RUN, "place_ids": ["g2"]}, headers=HEADERS).status_code == 429
    api.advance(timedelta(days=1))
    assert api.client.post("/runs", json={**RUN, "place_ids": ["g2"]}, headers=HEADERS).status_code == 202


def test_concurrent_requests_cannot_get_past_the_daily_limit() -> None:
    places = [cafe(f"g{index}") for index in range(5)]
    api = Api(known=places, runs_per_day=1)
    api.setup.google.delay = 0.05

    def post(place_id: str) -> int:
        body = {**RUN, "place_ids": [place_id]}
        return int(api.client.post("/runs", json=body, headers=HEADERS).status_code)

    with ThreadPoolExecutor(5) as pool:
        codes = sorted(pool.map(post, [place.external_id for place in places]))
    assert codes == [202, 429, 429, 429, 429]
    assert len(api.queue.enqueued) == 1
