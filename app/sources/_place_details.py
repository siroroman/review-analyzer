from app.domain import Place, PlaceDetails, Source
from app.gateway import GET_PLACE_DETAILS, ClientError, PlaceDetailsLookup
from app.sources._fetch import ScrapingGateway

_SERVICE = "gosom"


class PlaceDetailsSource:
    """Fetches the totals and business data of a Google Maps Place through the `gateway` (service `gosom`)."""

    def __init__(self, gateway: ScrapingGateway) -> None:
        self._gateway = gateway

    def fetch_place_details(self, place: Place, *, run_id: str) -> PlaceDetails:
        """The details of one Google Maps Place, found by its Place ID. The call costs 0 Budget.

        Raises `ValueError` for a Place of another Source; `GatewayDenied` and the provider's
        `ClientError` (`not_found` and `ambiguous` among them) pass through. A caller that can go on
        without details catches them.
        """
        if place.source is not Source.GOOGLE_MAPS:
            raise ValueError(f"no details for the Source {place.source.value}")
        response = self._gateway.call(
            _SERVICE, GET_PLACE_DETAILS, PlaceDetailsLookup(place.external_id), run_id=run_id
        )
        if not isinstance(response.payload, PlaceDetails):
            raise ClientError("bad_response")
        return response.payload
