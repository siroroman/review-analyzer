"""Places: autocomplete, branches of a chain and the user-confirmed set of Places that is a Company."""

from app.gateway import Suggestion
from app.places._places import Places
from app.places._types import (
    EmptyCompany,
    FakeOtherSource,
    InvalidCompany,
    OtherSourceSearch,
    OtherSourceUnavailable,
    PlaceNotFound,
    PlacesUnavailable,
)

__all__ = [
    "EmptyCompany",
    "FakeOtherSource",
    "InvalidCompany",
    "OtherSourceSearch",
    "OtherSourceUnavailable",
    "PlaceNotFound",
    "Places",
    "PlacesUnavailable",
    "Suggestion",
]
