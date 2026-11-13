import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime

from pydantic import SecretStr

from app.budget import Units
from app.gateway._provider import error_kind
from app.gateway._types import ClientError, ClientResponse, ClientTimeout, Usage
from app.transport import HttpError, HttpRequest, HttpTimeout, HttpTransport

SERVICE = "apify"
SCRAPE_GOOGLE_REVIEWS = "scrape_google_reviews"
_UNIT = "review"
_ACTOR = "compass~google-maps-reviews-scraper"
_URL = f"https://api.apify.com/v2/acts/{_ACTOR}/run-sync-get-dataset-items"
_LANGUAGE = "cs"


@dataclass(frozen=True)
class ReviewScrape:
    """The request of operation `scrape_google_reviews`: newest Reviews of one Google Place.

    `since` is inclusive; `limit` is the most Reviews the run may return and the size of its estimate.
    """

    place_id: str
    since: date | None
    limit: int


@dataclass(frozen=True)
class ScrapedReview:
    """One Google Maps Review as the actor delivered it, with the date parsed. Untrusted text."""

    place_id: str
    review_id: str
    stars: int
    text: str
    published_at: datetime
    language: str | None


def _field[T](item: Mapping[str, object], name: str, kind: type[T]) -> T:
    value = item.get(name)
    if isinstance(value, bool) or not isinstance(value, kind):
        raise ClientError("schema_changed")
    return value


def _scraped(item: object) -> ScrapedReview:
    """One dataset item, or `schema_changed` when a field the adapter relies on is missing or off."""
    if not isinstance(item, dict):
        raise ClientError("schema_changed")
    place_id = _field(item, "placeId", str)
    review_id = _field(item, "reviewId", str)
    stars = _field(item, "stars", int)
    published = _field(item, "publishedAtDate", str)
    if not place_id or not review_id or not 1 <= stars <= 5:
        raise ClientError("schema_changed")
    try:
        published_at = datetime.fromisoformat(published)
    except ValueError:
        raise ClientError("schema_changed") from None
    if published_at.tzinfo is None:
        raise ClientError("schema_changed")
    language = item.get("language")
    if language is not None and not isinstance(language, str):
        raise ClientError("schema_changed")
    return ScrapedReview(
        place_id, review_id, stars, _field(item, "text", str), published_at, language or None
    )


class ApifyClient:
    """ServiceClient `apify`: Google Maps Reviews through the compass actor, run synchronously.

    Operation `scrape_google_reviews`. The estimate is the request's `limit`, so the Budget is
    reserved for the most the run may deliver before it starts. The answer is a tuple of
    `ScrapedReview`; one item that does not fit the schema fails the whole call as `schema_changed`,
    and the Reviews already charged are reported on the error. The token is a `SecretStr`, sent only
    in a header, and never leaves this class.
    """

    def __init__(self, token: SecretStr, transport: HttpTransport, *, timeout: float = 300) -> None:
        self._token = token
        self._transport = transport
        self._timeout = timeout

    def estimate(self, operation: str, request: object) -> Usage:
        return Units(SERVICE, _UNIT, _scrape(operation, request).limit)

    def call(self, operation: str, request: object) -> ClientResponse:
        asked = _scrape(operation, request)
        data = self._run(asked)
        usage = Units(SERVICE, _UNIT, len(data))
        try:
            reviews = tuple(_scraped(item) for item in data)
        except ClientError as failure:
            raise ClientError(failure.kind, usage) from None
        return ClientResponse(reviews, usage)

    def _run(self, asked: ReviewScrape) -> list[object]:
        body: dict[str, object] = {
            "placeIds": [asked.place_id],
            "maxReviews": asked.limit,
            "reviewsSort": "newest",
            "language": _LANGUAGE,
        }
        if asked.since is not None:
            body["reviewsStartDate"] = asked.since.isoformat()
        request = HttpRequest(
            "POST",
            _URL,
            {"Authorization": f"Bearer {self._token.get_secret_value()}", "Content-Type": "application/json"},
            json.dumps(body).encode(),
            self._timeout,
        )
        try:
            response = self._transport.send(request)
        except HttpTimeout:
            # The run goes on at Apify and is billed per Review: book the most it can cost.
            raise ClientTimeout(Units(SERVICE, _UNIT, asked.limit)) from None
        except HttpError:
            raise ClientError("connection_error") from None
        if response.status == 408:  # Apify's own sync-run timeout: the run is still billed
            raise ClientError("timeout", Units(SERVICE, _UNIT, asked.limit))
        if response.status not in (200, 201):
            raise ClientError(error_kind(response.status))
        try:
            parsed = json.loads(response.body)
        except ValueError:
            raise ClientError("bad_response") from None
        if not isinstance(parsed, list):
            raise ClientError("bad_response")
        return parsed


def _scrape(operation: str, request: object) -> ReviewScrape:
    if operation != SCRAPE_GOOGLE_REVIEWS:
        raise ClientError("unsupported_operation")
    if not isinstance(request, ReviewScrape) or request.limit < 1 or not request.place_id:
        raise ClientError("bad_request")
    return request
