import pytest

from app.domain import PlaceDetails, Source
from app.storage import Storage, UnknownPlace
from tests.storage.helpers import company, place

DETAILS = PlaceDetails(
    rating=4.3,
    review_count=26348,
    reviews_per_rating={1: 1752, 2: 653, 3: 1939, 4: 5468, 5: 16536},
    category="Obchod s elektronikou",
    phone="+420 225 340 130",
)


def test_a_place_has_no_details_until_they_are_stored(storage: Storage) -> None:
    storage.companies.get_or_create(company(place("g1")))

    assert storage.companies.place_details(Source.GOOGLE_MAPS, "g1") is None


def test_stored_details_come_back_equal(storage: Storage) -> None:
    storage.companies.get_or_create(company(place("g1")))

    storage.companies.set_place_details(Source.GOOGLE_MAPS, "g1", DETAILS)

    assert storage.companies.place_details(Source.GOOGLE_MAPS, "g1") == DETAILS


def test_details_of_a_refresh_replace_the_old_ones(storage: Storage) -> None:
    storage.companies.get_or_create(company(place("g1")))
    storage.companies.set_place_details(Source.GOOGLE_MAPS, "g1", DETAILS)
    newer = PlaceDetails(rating=4.4, review_count=26400)

    storage.companies.set_place_details(Source.GOOGLE_MAPS, "g1", newer)

    assert storage.companies.place_details(Source.GOOGLE_MAPS, "g1") == newer


def test_details_belong_to_the_place_not_to_a_company(storage: Storage) -> None:
    storage.companies.get_or_create(company(place("g1")))
    storage.companies.get_or_create(company(place("g1"), place("g2")))
    storage.companies.set_place_details(Source.GOOGLE_MAPS, "g1", DETAILS)

    assert storage.companies.place_details(Source.GOOGLE_MAPS, "g2") is None
    assert storage.companies.place_details(Source.GOOGLE_MAPS, "g1") == DETAILS


def test_details_of_an_unknown_place_are_refused(storage: Storage) -> None:
    with pytest.raises(UnknownPlace):
        storage.companies.set_place_details(Source.GOOGLE_MAPS, "nope", DETAILS)
    assert storage.companies.place_details(Source.GOOGLE_MAPS, "nope") is None


def test_a_place_seen_again_keeps_its_details(storage: Storage) -> None:
    storage.companies.get_or_create(company(place("g1")))
    storage.companies.set_place_details(Source.GOOGLE_MAPS, "g1", DETAILS)

    storage.companies.get_or_create(company(place("g1"), place("g2")))

    assert storage.companies.place_details(Source.GOOGLE_MAPS, "g1") == DETAILS
