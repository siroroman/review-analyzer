import json
from datetime import UTC, date, datetime
from pathlib import Path

import pytest
from pydantic import SecretStr

from app.gateway import ApifyClient, ClientError, ClientTimeout, ReviewScrape, ScrapedReview, Units
from app.transport import FakeTransport, HttpError, HttpResponse, HttpTimeout

KEY = "not-a-real-value"
GOOGLE_FIXTURE = Path(__file__).parents[1] / "fixtures/sources/google_maps/2026-11-13-camp-velo.json"
PLACE = "ChIJcYfUFDm1ckcRizeMvL_POzQ"


def items() -> list[dict[str, object]]:
    parsed = json.loads(GOOGLE_FIXTURE.read_text())
    assert isinstance(parsed, list)
    return parsed


def answer(body: object, status: int = 200) -> HttpResponse:
    return HttpResponse(status, json.dumps(body).encode())


def client(*steps: HttpResponse | HttpError) -> tuple[ApifyClient, FakeTransport]:
    transport = FakeTransport(*steps)
    return ApifyClient(SecretStr(KEY), transport), transport


def scrape(since: date | None = None, limit: int = 20) -> ReviewScrape:
    return ReviewScrape(PLACE, since, limit)


def test_every_review_of_the_recorded_run_is_mapped() -> None:
    adapter, _ = client(answer(items()))
    response = adapter.call("scrape_google_reviews", scrape())
    reviews = response.payload
    assert isinstance(reviews, tuple) and len(reviews) == 20
    first = reviews[0]
    assert first == ScrapedReview(
        place_id=PLACE,
        review_id="Ci9DQUlRQUNvZENodHljRjlvT201R09EQjFlbkJIVDB0Qk9EaEJOVlV4ZVRkU2VVRRAB",
        stars=3,
        text="Anonymized review text 1.",
        published_at=datetime(2026, 10, 30, 9, 46, 30, 439000, tzinfo=UTC),
        language="cs",
    )
    assert reviews[1].text == ""  # a Review with only stars is delivered, sanitize decides about it


def test_usage_is_the_number_of_reviews_returned() -> None:
    adapter, _ = client(answer(items()[:7]))
    assert adapter.call("scrape_google_reviews", scrape()).usage == Units("apify", "review", 7)


def test_an_empty_result_is_a_valid_answer_that_costs_nothing() -> None:
    adapter, _ = client(answer([]))
    response = adapter.call("scrape_google_reviews", scrape())
    assert response.payload == ()
    assert response.usage == Units("apify", "review", 0)


def test_the_estimate_is_the_limit_so_the_budget_is_reserved_before_the_run() -> None:
    adapter, transport = client()
    assert adapter.estimate("scrape_google_reviews", scrape(limit=150)) == Units("apify", "review", 150)
    assert transport.requests == []


def test_sends_the_actor_input_newest_first_with_the_token_in_a_header() -> None:
    adapter, transport = client(answer([]))
    adapter.call("scrape_google_reviews", scrape(since=date(2026, 9, 1), limit=50))
    sent = transport.requests[0]
    assert sent.method == "POST"
    assert sent.url.startswith("https://api.apify.com/v2/acts/compass~google-maps-reviews-scraper/")
    assert "run-sync-get-dataset-items" in sent.url
    assert KEY not in sent.url
    assert sent.headers["Authorization"] == f"Bearer {KEY}"
    body = json.loads(sent.body)
    assert body["placeIds"] == [PLACE]
    assert body["maxReviews"] == 50
    assert body["reviewsSort"] == "newest"
    assert body["reviewsStartDate"] == "2026-09-01"
    assert body["language"] == "cs"


def test_without_since_the_start_date_is_not_sent() -> None:
    adapter, transport = client(answer([]))
    adapter.call("scrape_google_reviews", scrape())
    assert "reviewsStartDate" not in json.loads(transport.requests[0].body)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("reviewId", None),
        ("stars", "five"),
        ("stars", 9),
        ("publishedAtDate", "yesterday"),
        ("publishedAtDate", None),
        ("placeId", ""),
        ("text", 5),
    ],
)
def test_a_changed_schema_is_a_failure_that_still_reports_the_charge(field: str, value: object) -> None:
    data = items()[:3]
    data[1][field] = value
    adapter, _ = client(answer(data))
    with pytest.raises(ClientError) as raised:
        adapter.call("scrape_google_reviews", scrape())
    assert raised.value.kind == "schema_changed"
    assert raised.value.usage == Units("apify", "review", 3)


def test_a_missing_field_is_a_changed_schema() -> None:
    data = items()[:2]
    del data[0]["publishedAtDate"]
    adapter, _ = client(answer(data))
    with pytest.raises(ClientError) as raised:
        adapter.call("scrape_google_reviews", scrape())
    assert raised.value.kind == "schema_changed"


def test_an_answer_that_is_not_a_list_is_a_bad_response() -> None:
    adapter, _ = client(answer({"error": {"type": "run-failed"}}))
    with pytest.raises(ClientError) as raised:
        adapter.call("scrape_google_reviews", scrape())
    assert raised.value.kind == "bad_response"


def test_invalid_json_is_a_bad_response() -> None:
    adapter, _ = client(HttpResponse(200, b"<html>"))
    with pytest.raises(ClientError) as raised:
        adapter.call("scrape_google_reviews", scrape())
    assert raised.value.kind == "bad_response"


@pytest.mark.parametrize(
    ("status", "kind"),
    [(401, "auth"), (402, "payment"), (429, "rate_limited"), (400, "bad_request"), (503, "server_error")],
)
def test_an_error_status_becomes_a_short_kind(status: int, kind: str) -> None:
    adapter, _ = client(answer({"error": {"message": f"secret {KEY}"}}, status))
    with pytest.raises(ClientError) as raised:
        adapter.call("scrape_google_reviews", scrape())
    assert raised.value.kind == kind
    assert KEY not in str(raised.value)


def test_a_timeout_is_a_client_timeout() -> None:
    adapter, _ = client(HttpTimeout())
    with pytest.raises(ClientTimeout):
        adapter.call("scrape_google_reviews", scrape())


def test_a_connection_failure_is_a_connection_error() -> None:
    adapter, _ = client(HttpError())
    with pytest.raises(ClientError) as raised:
        adapter.call("scrape_google_reviews", scrape())
    assert raised.value.kind == "connection_error"


def test_another_operation_or_request_is_refused_before_any_call() -> None:
    adapter, transport = client()
    with pytest.raises(ClientError) as wrong_operation:
        adapter.call("complete", scrape())
    with pytest.raises(ClientError) as wrong_request:
        adapter.estimate("scrape_google_reviews", "not a request")
    assert wrong_operation.value.kind == "unsupported_operation"
    assert wrong_request.value.kind == "bad_request"
    assert transport.requests == []


def test_a_non_positive_limit_is_refused() -> None:
    adapter, transport = client()
    with pytest.raises(ClientError) as raised:
        adapter.estimate("scrape_google_reviews", scrape(limit=0))
    assert raised.value.kind == "bad_request"
    assert transport.requests == []
