import json
from pathlib import Path

import pytest
from pydantic import SecretStr

from app.domain import Place, Source
from app.gateway import ClientError, ClientTimeout, Units
from app.places import (
    AutocompleteRequest,
    DetailsRequest,
    GooglePage,
    GooglePlacesClient,
    Suggestion,
    TextSearchRequest,
)
from app.transport import FakeTransport, HttpError, HttpResponse, HttpTimeout
from tests.adapters.helpers import body_of, fixture

KEY = "not-a-real-key"
RECORDED = Path(__file__).parents[1] / "fixtures" / "places" / "2026-11-13-text-search-globus.json"
# The autocomplete and details fixtures are written from the Places API (New) reference, not recorded;
# the text search ones are cut from the real response recorded on 2026-11-13.


def client(*steps: HttpResponse | HttpError) -> tuple[GooglePlacesClient, FakeTransport]:
    transport = FakeTransport(*steps)
    return GooglePlacesClient(SecretStr(KEY), transport), transport


def test_autocomplete_keeps_only_place_predictions() -> None:
    adapter, _ = client(fixture("google_places_autocomplete_ok.json"))
    response = adapter.call("autocomplete", AutocompleteRequest("globus"))
    assert response.payload == (
        Suggestion("ChIJ_RjZFHvsC0cRk0DRRqTuJlA", "Globus Hypermarket, Kostelecká, Praha-Čakovice, Česko"),
        Suggestion("ChIJcYfUFDm1ckcRizeMvL_POzQ", "CAMP VELO, Vratěnín, Česko"),
    )
    assert response.usage == Units("google_places", "autocomplete_request", 1)


def test_autocomplete_without_suggestions_is_empty() -> None:
    adapter, _ = client(HttpResponse(200, b"{}"))
    assert adapter.call("autocomplete", AutocompleteRequest("zzzz")).payload == ()


def test_autocomplete_sends_the_key_a_field_mask_and_the_czech_bias() -> None:
    adapter, transport = client(fixture("google_places_autocomplete_ok.json"))
    adapter.call("autocomplete", AutocompleteRequest("globus"))
    sent = transport.requests[0]
    assert sent.method == "POST"
    assert sent.url == "https://places.googleapis.com/v1/places:autocomplete"
    assert sent.headers["X-Goog-Api-Key"] == KEY
    assert "suggestions.placePrediction.placeId" in sent.headers["X-Goog-FieldMask"]
    assert body_of(sent.body) == {"input": "globus", "languageCode": "cs", "regionCode": "CZ"}


def test_details_is_a_place_on_google_maps() -> None:
    adapter, transport = client(fixture("google_places_details_ok.json"))
    response = adapter.call("details", DetailsRequest("ChIJ_RjZFHvsC0cRk0DRRqTuJlA"))
    assert response.payload == Place(
        source=Source.GOOGLE_MAPS,
        external_id="ChIJ_RjZFHvsC0cRk0DRRqTuJlA",
        name="Globus Hypermarket",
        address="Kostelecká 823, 196 00 Praha-Čakovice",
    )
    assert response.usage == Units("google_places", "details_request", 1)
    sent = transport.requests[0]
    assert sent.method == "GET"
    assert sent.url == "https://places.googleapis.com/v1/places/ChIJ_RjZFHvsC0cRk0DRRqTuJlA?languageCode=cs"
    assert sent.headers["X-Goog-FieldMask"] == "id,displayName,formattedAddress"


def test_a_place_id_that_is_not_an_id_never_reaches_the_url() -> None:
    adapter, transport = client()
    with pytest.raises(ClientError) as failure:
        adapter.call("details", DetailsRequest("x/../../other?key=1"))
    assert failure.value.kind == "bad_request"
    assert transport.requests == []


def test_text_search_is_a_page_of_places_with_the_next_page() -> None:
    adapter, transport = client(fixture("google_places_text_search_page1.json"))
    page = adapter.call("text_search", TextSearchRequest("Globus Hypermarket")).payload
    assert isinstance(page, GooglePage)
    assert [place.external_id for place in page.places] == [
        "ChIJJQOrL4qTC0cRZwhAPs8W0c0",
        "ChIJ_RjZFHvsC0cRk0DRRqTuJlA",
        "ChIJ-1MNFg2-C0cRXyQmrJxu0o0",
    ]
    assert page.places[1].name == "Globus Hypermarket"
    assert page.places[1].address == "Kostelecká 823, 196 00 Praha-Čakovice"
    assert page.next_page == "page-2-token"
    body = body_of(transport.requests[0].body)
    assert body == {
        "textQuery": "Globus Hypermarket",
        "regionCode": "CZ",
        "languageCode": "cs",
        "pageSize": 20,
    }
    assert "places.id" in transport.requests[0].headers["X-Goog-FieldMask"]


def test_text_search_continues_with_the_page() -> None:
    adapter, transport = client(fixture("google_places_text_search_page2.json"))
    page = adapter.call("text_search", TextSearchRequest("Globus Hypermarket", "page-2-token")).payload
    assert isinstance(page, GooglePage)
    assert page.next_page is None
    assert body_of(transport.requests[0].body)["pageToken"] == "page-2-token"


def test_text_search_reads_the_recorded_response_of_2026_11_13() -> None:
    recorded = json.loads(RECORDED.read_text())
    adapter, _ = client(HttpResponse(200, json.dumps({"places": recorded}).encode()))
    page = adapter.call("text_search", TextSearchRequest("Globus Hypermarket")).payload
    assert isinstance(page, GooglePage)
    assert len(page.places) == 15
    assert page.places[0].name == "Globus Hypermarket"


def test_text_search_without_a_result_is_an_empty_page() -> None:
    adapter, _ = client(HttpResponse(200, b"{}"))
    page = adapter.call("text_search", TextSearchRequest("nothing here")).payload
    assert page == GooglePage((), None)


@pytest.mark.parametrize(
    ("status", "kind"),
    [
        (404, "not_found"),
        (429, "rate_limited"),
        (500, "unavailable"),
        (503, "unavailable"),
        (403, "rejected"),
    ],
)
def test_a_failed_status_is_a_client_error_of_one_kind(status: int, kind: str) -> None:
    adapter, _ = client(HttpResponse(status, b'{"error": {"message": "key not-a-real-key"}}'))
    with pytest.raises(ClientError) as failure:
        adapter.call("details", DetailsRequest("ChIJabc"))
    assert failure.value.kind == kind
    assert KEY not in str(failure.value)
    assert failure.value.usage is None


def test_no_answer_is_a_timeout_or_a_network_error() -> None:
    adapter, _ = client(HttpTimeout("slow"), HttpError("down"))
    with pytest.raises(ClientTimeout):
        adapter.call("details", DetailsRequest("ChIJabc"))
    with pytest.raises(ClientError) as failure:
        adapter.call("details", DetailsRequest("ChIJabc"))
    assert failure.value.kind == "network"


@pytest.mark.parametrize("body", [b"not json", b"[]", b'{"suggestions": "x"}'])
def test_an_answer_that_is_not_the_documented_shape_is_a_bad_response(body: bytes) -> None:
    adapter, _ = client(HttpResponse(200, body))
    with pytest.raises(ClientError) as failure:
        adapter.call("autocomplete", AutocompleteRequest("x"))
    assert failure.value.kind == "bad_response"


def test_an_unknown_operation_or_request_is_refused_before_any_call() -> None:
    adapter, transport = client()
    with pytest.raises(ClientError) as unknown:
        adapter.call("reviews", AutocompleteRequest("x"))
    assert unknown.value.kind == "unsupported_operation"
    with pytest.raises(ClientError) as wrong:
        adapter.call("details", AutocompleteRequest("x"))
    assert wrong.value.kind == "bad_request"
    assert transport.requests == []


def test_the_estimate_is_one_request_of_the_operation() -> None:
    adapter, _ = client()
    assert adapter.estimate("autocomplete", AutocompleteRequest("x")) == Units(
        "google_places", "autocomplete_request", 1
    )
    assert adapter.estimate("details", DetailsRequest("ChIJabc")) == Units(
        "google_places", "details_request", 1
    )
    assert adapter.estimate("text_search", TextSearchRequest("x")) == Units(
        "google_places", "text_search_request", 1
    )


def test_a_request_never_shows_the_key() -> None:
    assert KEY not in repr(GooglePlacesClient(SecretStr(KEY), FakeTransport()))
