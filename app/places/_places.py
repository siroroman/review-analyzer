import re
import unicodedata
from collections.abc import Collection, Sequence
from difflib import SequenceMatcher

from app.domain import Company, Place
from app.gateway import BudgetExceeded, ClientError, Gateway, GatewayDenied
from app.places._google import SERVICE
from app.places._types import (
    AutocompleteRequest,
    DetailsRequest,
    EmptyCompany,
    GooglePage,
    OtherSourceSearch,
    OtherSourceUnavailable,
    PlaceNotFound,
    PlacesUnavailable,
    Suggestion,
    TextSearchRequest,
)

MAX_PAGES = 3  # Google lists at most 60 places for one query: 3 pages of 20.
MATCH_THRESHOLD = 0.6
_NAME_WEIGHT = 0.6
_WAIT = {"rate_limited", "concurrency_limit"}


def _normal(text: str) -> str:
    """Lower case, no diacritics, only letters and digits: "Kostelecká 823/77" -> "kostelecka 823 77"."""
    plain = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", " ", plain.casefold()).strip()


def _score(home: Place, candidate: Place) -> float:
    """0 to 1: the name by similarity of text, the address by the share of the shorter one that matches."""
    name = SequenceMatcher(None, _normal(home.name), _normal(candidate.name)).ratio()
    ours, theirs = set(_normal(home.address).split()), set(_normal(candidate.address).split())
    address = len(ours & theirs) / min(len(ours), len(theirs)) if ours and theirs else 0.0
    return _NAME_WEIGHT * name + (1 - _NAME_WEIGHT) * address


class Places:
    """Finds a Company: autocomplete, the branches of a chain and the Places the user confirms.

    Google Places is reached only through `Gateway.call` (service `google_places`). Whenever it cannot be
    used (outage, rate limit, Budget) the caller gets `PlacesUnavailable`, to show "try later", never a
    crash. `run_id` is the Run the Budget charges the calls to.
    """

    def __init__(self, gateway: Gateway, other_source: OtherSourceSearch) -> None:
        self._gateway = gateway
        self._other = other_source

    def suggest(self, query: str, *, run_id: str) -> list[Suggestion]:
        """Autocomplete lines for the text the user typed; a blank text makes no call."""
        if not query.strip():
            return []
        found = self._call("autocomplete", AutocompleteRequest(query.strip()), run_id)
        if not isinstance(found, tuple):
            raise PlacesUnavailable("bad_response")
        return [item for item in found if isinstance(item, Suggestion)]

    def resolve(self, place_id: str, *, run_id: str) -> Place:
        """The Google Maps Place with this id. Raises `PlaceNotFound` when Google has none."""
        found = self._call("details", DetailsRequest(place_id), run_id, not_found=True)
        if not isinstance(found, Place):
            raise PlacesUnavailable("bad_response")
        return found

    def branches(self, place: Place, *, run_id: str) -> list[Place]:
        """Candidate branches: a text search by the Place's name, the exact name first, itself left out.

        A chain also lists its restaurants and petrol stations (T14: about 5 of 15 results were
        hypermarkets), so these are only candidates; the user confirms them.
        """
        seen = {place.external_id}
        found: list[Place] = []
        token: str | None = None
        for _ in range(MAX_PAGES):
            page = self._call("text_search", TextSearchRequest(place.name, token), run_id)
            if not isinstance(page, GooglePage):
                raise PlacesUnavailable("bad_response")
            for candidate in page.places:
                if candidate.external_id not in seen:
                    seen.add(candidate.external_id)
                    found.append(candidate)
            token = page.next_page
            if token is None:
                break
        name = _normal(place.name)
        return sorted(found, key=lambda candidate: _normal(candidate.name) != name)

    def confirm(
        self,
        place_ids: Collection[str],
        *,
        name: str,
        industry: str,
        run_id: str,
        also: Sequence[Place] = (),
    ) -> Company:
        """The Company of the Google Maps ids the user confirmed, plus Places of other Sources.

        The same set of ids is the same Company in any order and with repeats (`Company.places_key`).
        An empty set raises `EmptyCompany`.
        """
        unique = tuple(dict.fromkeys(place_ids))
        if not unique and not also:
            raise EmptyCompany("a Company needs at least one Place")
        resolved = tuple(self.resolve(place_id, run_id=run_id) for place_id in unique)
        return Company(name=name, industry=industry, places=resolved + tuple(also))

    def match_other_sources(self, place: Place) -> list[Place]:
        """Candidates on the other Source (Firmy.cz) for this Place, best match by name and address first."""
        try:
            candidates = self._other.search(place.name, place.address)
        except OtherSourceUnavailable as unavailable:
            raise PlacesUnavailable("other_source_unavailable") from unavailable
        scored = [(_score(place, candidate), candidate) for candidate in candidates]
        kept = [(score, candidate) for score, candidate in scored if score >= MATCH_THRESHOLD]
        return [candidate for _, candidate in sorted(kept, key=lambda pair: -pair[0])]

    def _call(self, operation: str, request: object, run_id: str, *, not_found: bool = False) -> object:
        try:
            return self._gateway.call(SERVICE, operation, request, run_id=run_id).payload
        except BudgetExceeded as exceeded:
            raise PlacesUnavailable("budget_exceeded") from exceeded
        except GatewayDenied as denied:
            if denied.reason not in _WAIT:
                raise  # a configuration fault, not something to try later
            raise PlacesUnavailable(denied.reason, denied.retry_after) from denied
        except ClientError as failure:
            if not_found and failure.kind == "not_found":
                raise PlaceNotFound(request) from failure
            raise PlacesUnavailable(failure.kind) from failure
