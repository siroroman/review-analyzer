from tests.api.helpers import HEADERS, Api, cafe


def test_searching_and_confirming_never_use_up_one_shared_run_budget() -> None:
    places = [cafe(f"g{index}") for index in range(12)]
    api = Api(known=places, run_cap="0.1")  # a Details call costs about 0.017: a shared Run would stop at 5
    codes = [
        api.client.post(
            "/runs",
            json={"place_ids": [place.external_id]},
            headers=HEADERS,
        ).status_code
        for place in places
    ]
    assert codes == [202] * 12
    assert api.client.get("/places/suggest", params={"q": "kav"}, headers=HEADERS).status_code == 200
