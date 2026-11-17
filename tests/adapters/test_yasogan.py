import json
from dataclasses import fields
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from app.budget import estimate_cost
from app.gateway import (
    SCRAPE_GOOGLE_REVIEWS,
    ClientError,
    ClientTimeout,
    ScrapedReview,
    Units,
    YasogaNClient,
    YasogaNScrape,
)
from app.transport import FakeTransport, HttpError, HttpResponse, HttpTimeout

FIXTURE = Path(__file__).parents[1] / "fixtures/sources/google_maps/2026-11-17-yasogan-sample.json"
PLACE = "ChIJcYfUFDm1ckcRizeMvL_POzQ"
BASE = "https://yasogan.internal.example"


def items() -> list[dict[str, object]]:
    parsed = json.loads(FIXTURE.read_text())
    assert isinstance(parsed, list)
    return parsed


def answer(body: object, status: int = 200) -> HttpResponse:
    return HttpResponse(status, json.dumps(body).encode())


def client(*steps: HttpResponse | HttpError) -> tuple[YasogaNClient, FakeTransport]:
    transport = FakeTransport(*steps)
    return YasogaNClient(BASE, transport), transport


def scrape(limit: int = 20) -> YasogaNScrape:
    return YasogaNScrape(PLACE, limit)


def test_every_review_of_the_recorded_output_is_mapped() -> None:
    adapter, _ = client(answer(items()))
    reviews = adapter.call(SCRAPE_GOOGLE_REVIEWS, scrape()).payload
    assert isinstance(reviews, tuple) and len(reviews) == 5
    assert reviews[0] == ScrapedReview(
        review_id="Ci9DQUlRQUNvZENodHljRjlvT201R09EQjFlbkJIVDB0Qk9EaEJOVlV4ZVRkU2VVRRAB",
        stars=3,
        text="Anonymized review text 1.",
        published_at=datetime(2026, 10, 30, 9, 46, 30, 439000, tzinfo=UTC),
    )


def test_a_review_with_only_stars_comes_back_with_empty_text_and_its_rating() -> None:
    adapter, _ = client(answer(items()))
    reviews = adapter.call(SCRAPE_GOOGLE_REVIEWS, scrape()).payload
    assert isinstance(reviews, tuple)
    assert (reviews[1].text, reviews[1].stars) == ("", 5)  # the real output has `text: null` here


def test_a_br_tag_becomes_a_line_break() -> None:
    adapter, _ = client(answer(items()))
    reviews = adapter.call(SCRAPE_GOOGLE_REVIEWS, scrape()).payload
    assert isinstance(reviews, tuple)
    assert reviews[4].text == "Anonymized\nreview text 5."


def test_no_author_field_reaches_the_result() -> None:
    assert [f.name for f in fields(ScrapedReview)] == ["review_id", "stars", "text", "published_at"]
    adapter, _ = client(answer(items()))
    reviews = adapter.call(SCRAPE_GOOGLE_REVIEWS, scrape()).payload
    assert isinstance(reviews, tuple)
    assert not any("Anonymized Author" in repr(review) or "contrib" in repr(review) for review in reviews)


def test_usage_is_the_number_of_reviews_returned_and_it_costs_nothing() -> None:
    adapter, _ = client(answer(items()[:3]))
    usage = adapter.call(SCRAPE_GOOGLE_REVIEWS, scrape()).usage
    assert usage == Units("yasogan", "review", 3)
    assert estimate_cost(usage) == Decimal(0)


def test_the_timestamp_is_a_string_of_milliseconds_in_the_real_output_and_a_number_is_accepted_too() -> None:
    data = items()[:2]
    assert data[0]["time"]["published"] == "1793353590439"  # type: ignore[index]
    data[1]["time"]["published"] = 1793353590439  # type: ignore[index]
    adapter, _ = client(answer(data))
    reviews = adapter.call(SCRAPE_GOOGLE_REVIEWS, scrape()).payload
    assert isinstance(reviews, tuple)
    assert (
        reviews[0].published_at
        == reviews[1].published_at
        == datetime(2026, 10, 30, 9, 46, 30, 439000, tzinfo=UTC)
    )


def test_an_empty_answer_is_a_valid_empty_result() -> None:
    adapter, _ = client(answer([]))
    response = adapter.call(SCRAPE_GOOGLE_REVIEWS, scrape())
    assert response.payload == () and response.usage == Units("yasogan", "review", 0)


def test_the_estimate_is_the_limit_and_makes_no_request() -> None:
    adapter, transport = client()
    assert adapter.estimate(SCRAPE_GOOGLE_REVIEWS, scrape(150)) == Units("yasogan", "review", 150)
    assert transport.requests == []


@pytest.mark.parametrize(("limit", "pages"), [(1, 1), (10, 1), (11, 2), (1000, 100)])
def test_it_asks_for_newest_first_clean_text_and_one_page_per_ten_reviews(limit: int, pages: int) -> None:
    adapter, transport = client(answer([]))
    adapter.call(SCRAPE_GOOGLE_REVIEWS, scrape(limit))
    sent = transport.requests[0]
    assert (sent.method, sent.url) == ("POST", f"{BASE}/reviews")
    assert json.loads(sent.body) == {"place_id": PLACE, "pages": pages, "sort_type": "newest", "clean": True}


def test_a_base_url_with_a_trailing_slash_gives_the_same_url() -> None:
    transport = FakeTransport(answer([]))
    YasogaNClient(BASE + "/", transport).call(SCRAPE_GOOGLE_REVIEWS, scrape())
    assert transport.requests[0].url == f"{BASE}/reviews"


@pytest.mark.parametrize(
    "mutate",
    [
        lambda i: i.pop("review_id"),
        lambda i: i.update(review_id=""),
        lambda i: i["review"].update(rating=9),
        lambda i: i["review"].update(rating="five"),
        lambda i: i["review"].update(text=5),
        lambda i: i["time"].update(published="yesterday"),
        lambda i: i["time"].update(published=None),
        lambda i: i.pop("review"),
        lambda i: i.pop("time"),
    ],
)
def test_a_changed_schema_fails_the_call(mutate: object) -> None:
    data = items()[:3]
    assert callable(mutate)
    mutate(data[1])
    adapter, _ = client(answer(data))
    with pytest.raises(ClientError) as raised:
        adapter.call(SCRAPE_GOOGLE_REVIEWS, scrape())
    assert raised.value.kind == "schema_changed"


@pytest.mark.parametrize(("status", "kind"), [(401, "auth"), (429, "rate_limited"), (502, "server_error")])
def test_an_http_error_is_a_failure_with_its_kind(status: int, kind: str) -> None:
    adapter, _ = client(answer({}, status))
    with pytest.raises(ClientError) as raised:
        adapter.call(SCRAPE_GOOGLE_REVIEWS, scrape())
    assert (raised.value.kind, raised.value.usage) == (kind, None)


def test_a_timeout_and_a_connection_error_are_failures() -> None:
    adapter, _ = client(HttpTimeout(), HttpError())
    with pytest.raises(ClientTimeout):
        adapter.call(SCRAPE_GOOGLE_REVIEWS, scrape())
    with pytest.raises(ClientError) as raised:
        adapter.call(SCRAPE_GOOGLE_REVIEWS, scrape())
    assert raised.value.kind == "connection_error"


@pytest.mark.parametrize("body", [b"not json", b'{"reviews": []}'])
def test_an_answer_that_is_not_a_list_is_a_bad_response(body: bytes) -> None:
    adapter, _ = client(HttpResponse(200, body))
    with pytest.raises(ClientError) as raised:
        adapter.call(SCRAPE_GOOGLE_REVIEWS, scrape())
    assert raised.value.kind == "bad_response"


def test_another_operation_and_a_bad_request_are_refused_before_any_call() -> None:
    adapter, transport = client()
    with pytest.raises(ClientError, match="unsupported_operation"):
        adapter.call("other", scrape())
    with pytest.raises(ClientError, match="bad_request"):
        adapter.call(SCRAPE_GOOGLE_REVIEWS, YasogaNScrape(PLACE, 0))
    with pytest.raises(ClientError, match="bad_request"):
        adapter.call(SCRAPE_GOOGLE_REVIEWS, "x")
    assert transport.requests == []
