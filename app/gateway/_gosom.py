import json
from dataclasses import dataclass
from typing import Any

from pydantic import ValidationError

from app.budget import Units
from app.domain import PlaceDetails
from app.gateway._provider import error_kind
from app.gateway._types import ClientError, ClientResponse, ClientTimeout, Usage
from app.transport import HttpError, HttpRequest, HttpTimeout, HttpTransport

SERVICE = "gosom"
GET_PLACE_DETAILS = "get_place_details"
_UNIT = "place"
_LANGUAGE = "cs"
_DEPTH = 1  # one Place, no Reviews: the Reviews come only from the Reviews Source


@dataclass(frozen=True)
class PlaceDetailsLookup:
    """The request of operation `get_place_details`: one Place found by its Google Place ID (`ChIJ...`)."""

    place_id: str


def _optional_text(item: dict[str, Any], name: str) -> str | None:
    value = item.get(name)
    if value is None or value == "":
        return None
    if not isinstance(value, str):
        raise ClientError("schema_changed")
    return value


def _per_star(item: dict[str, Any]) -> dict[int, int] | None:
    value = item.get("reviews_per_rating")
    if value is None:
        return None
    if not isinstance(value, dict):
        raise ClientError("schema_changed")
    try:
        return {int(star): count for star, count in value.items()}
    except (ValueError, TypeError):
        raise ClientError("schema_changed") from None


def _details(item: dict[str, Any]) -> PlaceDetails:
    """The mapped Place, or `schema_changed` when a field we rely on is off. `user_reviews` is never read."""
    try:
        return PlaceDetails(
            rating=item.get("review_rating"),  # type: ignore[arg-type]  # pydantic rejects other kinds
            review_count=item.get("review_count"),  # type: ignore[arg-type]
            reviews_per_rating=_per_star(item),
            category=_optional_text(item, "category"),
            address=_optional_text(item, "address"),
            phone=_optional_text(item, "phone"),
            website=_optional_text(item, "website"),
            maps_url=_optional_text(item, "link"),
            thumbnail_url=_optional_text(item, "thumbnail"),
        )
    except ValidationError:
        raise ClientError("schema_changed") from None


def _choose(data: list[object], place_id: str) -> dict[str, Any]:
    """The one result for the asked Place: no result is `not_found`, no unique match is `ambiguous`."""
    items = [item for item in data if isinstance(item, dict)]
    if len(items) != len(data):
        raise ClientError("schema_changed")
    if not items:
        raise ClientError("not_found")
    matching = [item for item in items if item.get("place_id") == place_id]
    if len(matching) == 1:
        return matching[0]
    if not matching and len(items) == 1 and "place_id" not in items[0]:
        return items[0]
    raise ClientError("ambiguous")


class GosomClient:
    """ServiceClient `gosom`: Place details of a Google Maps Place from the gosom sidecar over HTTP.

    Operation `get_place_details`, request `PlaceDetailsLookup`, answer a `PlaceDetails`. The sidecar is
    asked for one Place by Google Place ID (`-depth 1`, `-lang cs`). Several results are cut to the one
    with the asked Place ID; no result is `not_found` and no single match is `ambiguous`. The call costs 0
    (ADR 0008), the usage is one `place`.
    """

    def __init__(self, base_url: str, transport: HttpTransport, *, timeout: float = 120) -> None:
        self._url = f"{base_url.rstrip('/')}/place-details"
        self._transport = transport
        self._timeout = timeout

    def estimate(self, operation: str, request: object) -> Usage:
        _lookup(operation, request)
        return Units(SERVICE, _UNIT, 1)

    def call(self, operation: str, request: object) -> ClientResponse:
        asked = _lookup(operation, request)
        data = self._run(asked)
        return ClientResponse(_details(_choose(data, asked.place_id)), Units(SERVICE, _UNIT, 1))

    def _run(self, asked: PlaceDetailsLookup) -> list[object]:
        body = {"place_id": asked.place_id, "lang": _LANGUAGE, "depth": _DEPTH}
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


def _lookup(operation: str, request: object) -> PlaceDetailsLookup:
    if operation != GET_PLACE_DETAILS:
        raise ClientError("unsupported_operation")
    if not isinstance(request, PlaceDetailsLookup) or not request.place_id:
        raise ClientError("bad_request")
    return request
