"""ServiceClient `yasogan`: Google Maps Reviews from the YasogaN scraper sidecar (ADR-0008)."""

import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime

from app.budget import Units
from app.gateway._provider import error_kind
from app.gateway._types import ClientError, ClientResponse, ClientTimeout, Usage
from app.transport import HttpError, HttpRequest, HttpTimeout, HttpTransport

SERVICE = "yasogan"
SCRAPE_GOOGLE_REVIEWS = "scrape_google_reviews"
_UNIT = "review"
_PAGE_SIZE = 10
_BR = re.compile(r"<br\s*/?>", re.IGNORECASE)


@dataclass(frozen=True)
class YasogaNScrape:
    """The request of operation `scrape_google_reviews`: the newest Reviews of one Google Place.

    `limit` is the most Reviews the call may return and the size of its estimate.
    """

    place_id: str
    limit: int


@dataclass(frozen=True)
class ScrapedReview:
    """One Google Maps Review as the scraper delivered it. Untrusted text; no author data."""

    review_id: str
    stars: int
    text: str
    published_at: datetime


def _object(item: Mapping[str, object], name: str) -> Mapping[str, object]:
    value = item.get(name)
    if not isinstance(value, dict):
        raise ClientError("schema_changed")
    return value


def _millis(value: object) -> int:
    """Unix time in milliseconds: the library delivers it as a string of digits, a number is accepted too."""
    if isinstance(value, str) and value.isascii() and value.isdigit():
        return int(value)
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    raise ClientError("schema_changed")


def _scraped(item: object) -> ScrapedReview:
    """One review object, or `schema_changed` when a field the adapter relies on is missing or off."""
    if not isinstance(item, dict):
        raise ClientError("schema_changed")
    review_id = item.get("review_id")
    published = _object(item, "time").get("published")
    body = _object(item, "review")
    stars = body.get("rating")
    text = body.get("text")
    if not isinstance(review_id, str) or not review_id:
        raise ClientError("schema_changed")
    if isinstance(stars, bool) or not isinstance(stars, int) or not 1 <= stars <= 5:
        raise ClientError("schema_changed")
    millis = _millis(published)
    if text is not None and not isinstance(text, str):
        raise ClientError("schema_changed")
    try:
        published_at = datetime.fromtimestamp(millis / 1000, UTC)
    except (OverflowError, OSError, ValueError):
        raise ClientError("schema_changed") from None
    return ScrapedReview(review_id, stars, _BR.sub("\n", text or ""), published_at)


class YasogaNClient:
    """ServiceClient `yasogan`: `POST {base_url}/reviews` on the private sidecar, newest Reviews first.

    Operation `scrape_google_reviews`. The sidecar gets `place_id`, `pages` (one per ten Reviews),
    `sort_type: "newest"` and `clean: true`, and answers a JSON list of review objects. The cost is 0
    (ADR-0008); usage is the number of Reviews returned. One item that does not fit the schema fails the
    whole call as `schema_changed`. Authentication of the sidecar is its deployment's business (#128).
    """

    def __init__(self, base_url: str, transport: HttpTransport, *, timeout: float = 120) -> None:
        self._url = f"{base_url.rstrip('/')}/reviews"
        self._transport = transport
        self._timeout = timeout

    def estimate(self, operation: str, request: object) -> Usage:
        return Units(SERVICE, _UNIT, _scrape(operation, request).limit)

    def call(self, operation: str, request: object) -> ClientResponse:
        asked = _scrape(operation, request)
        data = self._run(asked)
        reviews = tuple(_scraped(item) for item in data)
        return ClientResponse(reviews, Units(SERVICE, _UNIT, len(reviews)))

    def _run(self, asked: YasogaNScrape) -> list[object]:
        body = {
            "place_id": asked.place_id,
            "pages": -(-asked.limit // _PAGE_SIZE),
            "sort_type": "newest",
            "clean": True,
        }
        request = HttpRequest(
            "POST", self._url, {"Content-Type": "application/json"}, json.dumps(body).encode(), self._timeout
        )
        try:
            response = self._transport.send(request)
        except HttpTimeout:
            raise ClientTimeout() from None
        except HttpError:
            raise ClientError("connection_error") from None
        if response.status != 200:
            raise ClientError(error_kind(response.status))
        try:
            parsed = json.loads(response.body)
        except ValueError:
            raise ClientError("bad_response") from None
        if not isinstance(parsed, list):
            raise ClientError("bad_response")
        return parsed


def _scrape(operation: str, request: object) -> YasogaNScrape:
    if operation != SCRAPE_GOOGLE_REVIEWS:
        raise ClientError("unsupported_operation")
    if not isinstance(request, YasogaNScrape) or request.limit < 1 or not request.place_id:
        raise ClientError("bad_request")
    return request
