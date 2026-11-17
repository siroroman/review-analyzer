import hashlib
from enum import StrEnum

from pydantic import Field, field_validator, model_validator

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


class PlaceDetails(DomainModel):
    """Totals and business data of one whole Place as its Source states them (not of the analyzed Reviews).

    Only `rating` and `review_count` are always there; everything else may be missing and is then `None`.
    `reviews_per_rating` maps a star (1 to 5) to its count and is kept as received: it is not forced to
    sum to `review_count`. The phone is the business's, never a person's.
    """

    rating: float = Field(ge=1, le=5)
    review_count: int = Field(ge=0)
    reviews_per_rating: dict[int, int] | None = None
    category: str | None = None
    address: str | None = None
    phone: str | None = None
    website: str | None = None
    maps_url: str | None = None
    thumbnail_url: str | None = None

    @field_validator("reviews_per_rating")
    @classmethod
    def _stars_one_to_five(cls, counts: dict[int, int] | None) -> dict[int, int] | None:
        if counts is not None and (
            any(star not in range(1, 6) for star in counts) or any(n < 0 for n in counts.values())
        ):
            raise ValueError("per star counts need stars 1 to 5 and no negative count")
        return counts


class PlaceResult(DomainModel):
    """What a Run says of one Place: the Source's own totals and how many Reviews were analyzed.

    `details` is `None` when the Source has none (Firmy.cz) or the call for them failed. `analyzed_count`
    counts stored Reviews of the Place that are not Flagged, Reviews without text included.
    `analyzed_is_limited` is true when the Place has more Reviews than were analyzed.
    """

    source: Source
    place_external_id: str = Field(min_length=1)
    details: PlaceDetails | None = None
    analyzed_count: int = Field(ge=0)
    analyzed_is_limited: bool


class Company(DomainModel):
    """A set of Places the user confirmed as belonging together; the same set is the same Company.

    The industry is unknown until the pipeline infers it from the downloaded Reviews.
    """

    name: str = Field(min_length=1)
    industry: str | None = Field(default=None, min_length=1)
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
