import json
from pathlib import Path

import pytest

from app.domain import PlaceDetails
from app.gateway import ClientError, ClientTimeout, GosomClient, PlaceDetailsLookup, Units
from app.transport import FakeTransport, HttpError, HttpResponse, HttpTimeout

# Recorded on 2026-11-17 from `gosom/google-maps-scraper:latest` (`-json -depth 1 -lang cs`, query "Alza.cz
# Showroom Praha 7"): one result of its output, with the names, photos and texts of the reviewers replaced.
FIXTURE = Path(__file__).parents[1] / "fixtures/places/gosom-place-details-alza-showroom.json"
PLACE = "ChIJvzXMT7CUC0cRvnSIfC_H8c4"
BASE = "http://gosom.internal:8080"


def results() -> list[dict[str, object]]:
    parsed = json.loads(FIXTURE.read_text())
    assert isinstance(parsed, list)
    return parsed


def answer(body: object, status: int = 200) -> HttpResponse:
    return HttpResponse(status, json.dumps(body).encode())


def client(*steps: HttpResponse | HttpError) -> tuple[GosomClient, FakeTransport]:
    transport = FakeTransport(*steps)
    return GosomClient(BASE, transport), transport


def details_of(*steps: HttpResponse | HttpError) -> PlaceDetails:
    adapter, _ = client(*steps)
    payload = adapter.call("get_place_details", PlaceDetailsLookup(PLACE)).payload
    assert isinstance(payload, PlaceDetails)
    return payload


def failure_of(*steps: HttpResponse | HttpError) -> ClientError:
    adapter, _ = client(*steps)
    with pytest.raises(ClientError) as raised:
        adapter.call("get_place_details", PlaceDetailsLookup(PLACE))
    return raised.value


def test_the_recorded_place_is_mapped_field_by_field() -> None:
    raw = results()[0]
    assert details_of(answer(results())) == PlaceDetails(
        rating=4.3,
        review_count=26347,
        reviews_per_rating={1: 1752, 2: 653, 3: 1939, 4: 5468, 5: 16535},
        category="Prodej elektroniky",
        address="Jateční 306/2, 170 00 Praha 7-Holešovice",
        phone="225 340 111",
        website="https://www.alza.cz/prodejna-praha-7-holesovice-595.htm",
        maps_url=str(raw["link"]),
        thumbnail_url=str(raw["thumbnail"]),
    )


def test_the_per_star_counts_of_the_fixture_sum_to_the_review_count() -> None:
    details = details_of(answer(results()))
    assert details.reviews_per_rating is not None
    assert sum(details.reviews_per_rating.values()) == details.review_count


def test_counts_that_do_not_sum_are_returned_as_received() -> None:
    item = results()[0] | {"reviews_per_rating": {"1": 1, "2": 1, "3": 1, "4": 1, "5": 1}}
    details = details_of(answer([item]))
    assert details.reviews_per_rating == {1: 1, 2: 1, 3: 1, 4: 1, 5: 1}
    assert details.review_count == 26347


@pytest.mark.parametrize(
    "name", ["category", "address", "phone", "web_site", "link", "thumbnail", "reviews_per_rating"]
)
def test_a_missing_optional_field_is_none(name: str) -> None:
    item = {key: value for key, value in results()[0].items() if key != name}
    details = details_of(answer([item]))
    assert (
        getattr(
            details, {"link": "maps_url", "thumbnail": "thumbnail_url", "web_site": "website"}.get(name, name)
        )
        is None
    )


@pytest.mark.parametrize("value", [None, ""])
def test_a_null_or_empty_website_is_none(value: object) -> None:
    assert details_of(answer([results()[0] | {"web_site": value}])).website is None


def test_the_reviews_of_the_result_are_ignored() -> None:
    assert "user_reviews" not in details_of(answer(results())).model_dump()


@pytest.mark.parametrize("name", ["review_rating", "review_count"])
def test_a_missing_required_field_is_schema_changed(name: str) -> None:
    item = {key: value for key, value in results()[0].items() if key != name}
    assert failure_of(answer([item])).kind == "schema_changed"


@pytest.mark.parametrize("changes", [{"review_rating": "4.3"}, {"review_count": 1.5}, {"review_rating": 9}])
def test_a_required_field_of_the_wrong_kind_is_schema_changed(changes: dict[str, object]) -> None:
    assert failure_of(answer([results()[0] | changes])).kind == "schema_changed"


def test_a_malformed_per_star_map_is_schema_changed() -> None:
    assert failure_of(answer([results()[0] | {"reviews_per_rating": {"six": 1}}])).kind == "schema_changed"


def test_no_result_is_not_found() -> None:
    assert failure_of(answer([])).kind == "not_found"


def test_only_the_result_with_the_asked_place_id_is_used_among_several() -> None:
    other = results()[0] | {"place_id": "ChIJother", "review_rating": 1.0}
    assert details_of(answer([other, results()[0]])).rating == 4.3


def test_several_results_none_of_them_the_asked_place_are_ambiguous() -> None:
    first = results()[0] | {"place_id": "ChIJone"}
    second = results()[0] | {"place_id": "ChIJtwo"}
    assert failure_of(answer([first, second])).kind == "ambiguous"


def test_two_results_with_the_asked_place_id_are_ambiguous() -> None:
    assert failure_of(answer([results()[0], results()[0]])).kind == "ambiguous"


def test_one_result_without_a_place_id_is_taken_for_the_asked_one() -> None:
    item = {key: value for key, value in results()[0].items() if key != "place_id"}
    assert details_of(answer([item])).review_count == 26347


def test_usage_is_one_place() -> None:
    adapter, _ = client(answer(results()))
    assert adapter.call("get_place_details", PlaceDetailsLookup(PLACE)).usage == Units("gosom", "place", 1)
    assert adapter.estimate("get_place_details", PlaceDetailsLookup(PLACE)) == Units("gosom", "place", 1)


def test_the_request_asks_one_place_in_czech_at_depth_one() -> None:
    adapter, transport = client(answer(results()))
    adapter.call("get_place_details", PlaceDetailsLookup(PLACE))
    (request,) = transport.requests
    assert (request.method, request.url) == ("POST", f"{BASE}/place-details")
    assert json.loads(request.body or b"") == {"place_id": PLACE, "lang": "cs", "depth": 1}


@pytest.mark.parametrize(
    ("status", "kind"),
    [(429, "rate_limited"), (503, "server_error"), (404, "http_error"), (400, "bad_request")],
)
def test_an_http_error_status_is_a_failure_with_a_short_kind(status: int, kind: str) -> None:
    assert failure_of(answer([], status)).kind == kind


def test_an_unreachable_sidecar_is_a_connection_error() -> None:
    assert failure_of(HttpError()).kind == "connection_error"


def test_a_timeout_is_a_client_timeout() -> None:
    adapter, _ = client(HttpTimeout())
    with pytest.raises(ClientTimeout):
        adapter.call("get_place_details", PlaceDetailsLookup(PLACE))


@pytest.mark.parametrize("body", [b"not json", b'{"a": 1}'])
def test_a_body_that_is_not_a_list_is_a_bad_response(body: bytes) -> None:
    assert failure_of(HttpResponse(200, body)).kind == "bad_response"


def test_an_unknown_operation_or_request_is_refused_before_any_call() -> None:
    adapter, transport = client()
    with pytest.raises(ClientError) as operation:
        adapter.call("scrape", PlaceDetailsLookup(PLACE))
    with pytest.raises(ClientError) as request:
        adapter.call("get_place_details", "ChIJ")
    with pytest.raises(ClientError) as empty:
        adapter.call("get_place_details", PlaceDetailsLookup(""))
    assert [operation.value.kind, request.value.kind, empty.value.kind] == [
        "unsupported_operation",
        "bad_request",
        "bad_request",
    ]
    assert transport.requests == []
