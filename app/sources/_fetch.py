from datetime import UTC, date
from typing import Protocol

from app.domain import DatePrecision, Place, RawReview, Source
from app.gateway import SCRAPE_GOOGLE_REVIEWS, ClientError, GatewayResponse, ScrapedReview, YasogaNScrape

_SERVICE = "yasogan"


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
        language=None,
    )


class Sources:
    """Fetches the Reviews of a Place from its Source through the `gateway` (service `yasogan`)."""

    def __init__(self, gateway: ScrapingGateway) -> None:
        self._gateway = gateway

    def fetch_reviews(
        self,
        place: Place,
        since: date | None,
        limit: int,
        *,
        run_id: str,
        known_count: int | None = None,
    ) -> list[RawReview]:
        """At most `limit` Reviews of a Google Maps Place, newest first, written on or after `since`.

        The scraper has no date filter, so `since` is applied after the fetch. Reviews without text are
        kept (empty text). The date is the UTC day of the timestamp; Reviews of one day keep the order of
        their exact time. A Review delivered twice is returned once. The scraper gives no language, so
        it is `None`. An empty answer is an empty list, unless `known_count` says the Place has Reviews:
        then it is the source error `empty_first_page`, never silently 0 Reviews. Raises `ValueError`
        for a Place of another Source or a `limit` below one; `GatewayDenied`, `BudgetExceeded` and the
        provider's `ClientError` (`schema_changed` among them) pass through.
        """
        if place.source is not Source.GOOGLE_MAPS:
            raise ValueError(f"no adapter for the Source {place.source.value}")
        if limit < 1:
            raise ValueError("limit must be at least 1")
        response = self._gateway.call(
            _SERVICE, SCRAPE_GOOGLE_REVIEWS, YasogaNScrape(place.external_id, limit), run_id=run_id
        )
        payload = response.payload
        if not isinstance(payload, tuple):
            raise ClientError("bad_response")
        if not payload and known_count:
            raise ClientError("empty_first_page")
        unique = {item.review_id: item for item in payload if isinstance(item, ScrapedReview)}
        fresh = [item for item in unique.values() if since is None or _day(item) >= since]
        fresh.sort(key=lambda item: item.published_at, reverse=True)
        return [_raw(place, item) for item in fresh[:limit]]


def _day(item: ScrapedReview) -> date:
    return item.published_at.astimezone(UTC).date()
