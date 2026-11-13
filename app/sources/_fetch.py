from datetime import UTC, date
from typing import Protocol

from app.domain import DatePrecision, Place, RawReview, Source
from app.gateway import SCRAPE_GOOGLE_REVIEWS, ClientError, GatewayResponse, ReviewScrape, ScrapedReview

_SERVICE = "apify"


class ScrapingGateway(Protocol):
    """The part of `gateway.Gateway` that `sources` uses."""

    def call(self, service: str, operation: str, request: object, *, run_id: str) -> GatewayResponse: ...


def _raw(place: Place, scraped: ScrapedReview) -> RawReview:
    return RawReview(
        source=Source.GOOGLE_MAPS,
        place_external_id=place.external_id,
        external_id=scraped.review_id,
        rating=scraped.stars,
        text=scraped.text,
        published_on=scraped.published_at.astimezone(UTC).date(),
        date_precision=DatePrecision.DAY,
        language=scraped.language,
    )


class Sources:
    """Fetches the Reviews of a Place from its Source through the `gateway` (service `apify`)."""

    def __init__(self, gateway: ScrapingGateway) -> None:
        self._gateway = gateway

    def fetch_reviews(self, place: Place, since: date | None, limit: int, *, run_id: str) -> list[RawReview]:
        """At most `limit` Reviews of a Google Maps Place, newest first, written on or after `since`.

        The Budget is reserved for `limit` Reviews before the run starts. The date is the UTC day of the
        timestamp the scraper delivers. A Review the scraper delivers twice is returned once. Raises
        `ValueError` for a Place of another Source or a `limit` below one; `GatewayDenied`,
        `BudgetExceeded` and the provider's `ClientError` (`schema_changed` among them) pass through.
        """
        if place.source is not Source.GOOGLE_MAPS:
            raise ValueError(f"no adapter for the Source {place.source.value}")
        if limit < 1:
            raise ValueError("limit must be at least 1")
        response = self._gateway.call(
            _SERVICE, SCRAPE_GOOGLE_REVIEWS, ReviewScrape(place.external_id, since, limit), run_id=run_id
        )
        payload = response.payload
        if not isinstance(payload, tuple):
            raise ClientError("bad_response")
        reviews = {item.review_id: _raw(place, item) for item in payload if isinstance(item, ScrapedReview)}
        fresh = [r for r in reviews.values() if since is None or r.published_on >= since]
        fresh.sort(key=lambda r: r.published_on, reverse=True)
        return fresh[:limit]
