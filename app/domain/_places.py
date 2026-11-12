import hashlib
from enum import StrEnum

from pydantic import Field, model_validator

from app.domain._base import DomainModel


class Source(StrEnum):
    """A public site that hosts reviews."""

    GOOGLE_MAPS = "google_maps"
    FIRMY_CZ = "firmy_cz"


class Place(DomainModel):
    """One branch of a Company on one Source, identified by that Source's external ID."""

    source: Source
    external_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    address: str


class Company(DomainModel):
    """A set of Places the user confirmed as belonging together; the same set is the same Company."""

    name: str = Field(min_length=1)
    industry: str = Field(min_length=1)
    places: tuple[Place, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _places_are_unique(self) -> "Company":
        if len({_place_id(place) for place in self.places}) != len(self.places):
            raise ValueError("a Company lists each Place once")
        return self

    @property
    def places_key(self) -> str:
        """Hash of the sorted Place ids: the Company's identity, independent of order and name."""
        joined = "\n".join(sorted(_place_id(place) for place in self.places))
        return hashlib.sha256(joined.encode()).hexdigest()


def _place_id(place: Place) -> str:
    return f"{place.source.value}:{place.external_id}"
