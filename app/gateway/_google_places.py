"""ServiceClient `google_places`: Places API (New) autocomplete, details and text search."""

import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from pydantic import SecretStr, ValidationError

from app.budget import Units
from app.domain import Place, Source
from app.gateway._types import ClientError, ClientResponse, ClientTimeout, Usage
from app.transport import HttpError, HttpRequest, HttpResponse, HttpTimeout, HttpTransport

GOOGLE_PLACES = "google_places"
_BASE = "https://places.googleapis.com/v1"
_ID = re.compile(r"[A-Za-z0-9_-]{1,300}")
_PAGE_SIZE = 20
_UNITS = {
    "autocomplete": "autocomplete_request",
    "details": "details_request",
    "text_search": "text_search_request",
}
_STATUS_KIND = {404: "not_found", 429: "rate_limited"}


@dataclass(frozen=True)
class Suggestion:
    """One autocomplete line: a Google Maps place the user may pick."""

    place_id: str
    text: str


@dataclass(frozen=True)
class AutocompleteRequest:
    query: str


@dataclass(frozen=True)
class DetailsRequest:
    place_id: str


@dataclass(frozen=True)
class TextSearchRequest:
    query: str
    page: str | None = None


@dataclass(frozen=True)
class GooglePage:
    """One page of a text search, already mapped to Places."""

    places: tuple[Place, ...]
    next_page: str | None


class GooglePlacesClient:
    """Operations `autocomplete`, `details` and `text_search`, each one request of its own SKU.

    The key is a `SecretStr` and never leaves this class: not in a URL, a log or an error. Field masks
    ask only for what `places` uses, which keeps every call in the cheapest SKU that has it.
    """

    def __init__(self, api_key: SecretStr, transport: HttpTransport, *, timeout: float = 10) -> None:
        self._key = api_key
        self._transport = transport
        self._timeout = timeout

    def estimate(self, operation: str, request: object) -> Usage:
        unit = _UNITS.get(operation)
        if unit is None:
            raise ClientError("unsupported_operation")
        return Units(GOOGLE_PLACES, unit, 1)

    def call(self, operation: str, request: object) -> ClientResponse:
        usage = self.estimate(operation, request)
        if operation == "autocomplete" and isinstance(request, AutocompleteRequest):
            return ClientResponse(self._autocomplete(request), usage)
        if operation == "details" and isinstance(request, DetailsRequest):
            return ClientResponse(self._details(request), usage)
        if operation == "text_search" and isinstance(request, TextSearchRequest):
            return ClientResponse(self._text_search(request), usage)
        raise ClientError("bad_request")

    def _autocomplete(self, request: AutocompleteRequest) -> tuple[Suggestion, ...]:
        body = {"input": request.query, "languageCode": "cs", "regionCode": "CZ"}
        mask = "suggestions.placePrediction.placeId,suggestions.placePrediction.text.text"
        data = self._send("POST", f"{_BASE}/places:autocomplete", mask, body)
        suggestions = data.get("suggestions", [])
        if not isinstance(suggestions, list):
            raise ClientError("bad_response")
        found: list[Suggestion] = []
        for item in suggestions:
            prediction = item.get("placePrediction") if isinstance(item, dict) else None
            if prediction is None:
                continue  # a query prediction, not a place
            found.append(_suggestion(prediction))
        return tuple(found)

    def _details(self, request: DetailsRequest) -> Place:
        if not _ID.fullmatch(request.place_id):
            raise ClientError("bad_request")
        url = f"{_BASE}/places/{request.place_id}?languageCode=cs"
        return _place(self._send("GET", url, "id,displayName,formattedAddress", None))

    def _text_search(self, request: TextSearchRequest) -> GooglePage:
        body: dict[str, object] = {
            "textQuery": request.query,
            "regionCode": "CZ",
            "languageCode": "cs",
            "pageSize": _PAGE_SIZE,
        }
        if request.page is not None:
            body["pageToken"] = request.page
        mask = "places.id,places.displayName,places.formattedAddress,nextPageToken"
        data = self._send("POST", f"{_BASE}/places:searchText", mask, body)
        places = data.get("places", [])
        token = data.get("nextPageToken")
        if not isinstance(places, list) or not (token is None or isinstance(token, str)):
            raise ClientError("bad_response")
        return GooglePage(tuple(_place(item) for item in places), token or None)

    def _send(self, method: str, url: str, mask: str, body: Mapping[str, object] | None) -> dict[str, Any]:
        headers = {"X-Goog-Api-Key": self._key.get_secret_value(), "X-Goog-FieldMask": mask}
        payload = b""
        if body is not None:
            headers["Content-Type"] = "application/json"
            payload = json.dumps(body, ensure_ascii=False).encode()
        try:
            answer: HttpResponse = self._transport.send(
                HttpRequest(method, url, headers, payload, self._timeout)
            )
        except HttpTimeout as slow:
            raise ClientTimeout from slow
        except HttpError as down:
            raise ClientError("network") from down
        if answer.status >= 500:
            raise ClientError("unavailable")
        if answer.status != 200:
            raise ClientError(_STATUS_KIND.get(answer.status, "rejected"))
        try:
            data = json.loads(answer.body)
        except ValueError as invalid:
            raise ClientError("bad_response") from invalid
        if not isinstance(data, dict):
            raise ClientError("bad_response")
        return data


def _text(value: object) -> str:
    text = value.get("text") if isinstance(value, dict) else None
    if not isinstance(text, str) or not text:
        raise ClientError("bad_response")
    return text


def _suggestion(prediction: object) -> Suggestion:
    if not isinstance(prediction, dict) or not isinstance(prediction.get("placeId"), str):
        raise ClientError("bad_response")
    return Suggestion(prediction["placeId"], _text(prediction.get("text")))


def _place(item: object) -> Place:
    if not isinstance(item, dict):
        raise ClientError("bad_response")
    address = item.get("formattedAddress", "")
    try:
        return Place(
            source=Source.GOOGLE_MAPS,
            external_id=item.get("id"),  # type: ignore[arg-type]  # validated by the model
            name=_text(item.get("displayName")),
            address=address if isinstance(address, str) else "",
        )
    except ValidationError as invalid:
        raise ClientError("bad_response") from invalid
