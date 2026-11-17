import pytest
from pydantic import ValidationError

from app.domain import Company, Place, PlaceDetails, Source


def _place(external_id: str = "ChIJ1", source: Source = Source.GOOGLE_MAPS) -> Place:
    return Place(source=source, external_id=external_id, name="Pobočka Brno", address="Masarykova 1, Brno")


def test_place_round_trips_through_json() -> None:
    place = _place()

    assert Place.model_validate_json(place.model_dump_json()) == place


def test_place_json_uses_plain_values() -> None:
    assert _place().model_dump(mode="json") == {
        "source": "google_maps",
        "external_id": "ChIJ1",
        "name": "Pobočka Brno",
        "address": "Masarykova 1, Brno",
    }


def test_place_rejects_an_empty_external_id() -> None:
    with pytest.raises(ValidationError):
        _place(external_id="")


def test_place_rejects_an_unknown_source() -> None:
    with pytest.raises(ValidationError):
        Place.model_validate({"source": "yelp", "external_id": "1", "name": "n", "address": "a"})


def test_company_round_trips_through_json() -> None:
    company = Company(name="Acme", industry="retail", places=(_place("a"), _place("b")))

    assert Company.model_validate_json(company.model_dump_json()) == company


def test_company_with_the_same_places_has_the_same_key_in_any_order() -> None:
    first = Company(name="Acme", industry="retail", places=(_place("a"), _place("b")))
    second = Company(name="Acme s.r.o.", industry="retail", places=(_place("b"), _place("a")))

    assert first.places_key == second.places_key


def test_company_with_other_places_has_another_key() -> None:
    first = Company(name="Acme", industry="retail", places=(_place("a"),))
    second = Company(name="Acme", industry="retail", places=(_place("b"),))

    assert first.places_key != second.places_key


def test_the_same_external_id_on_another_source_is_another_place() -> None:
    google = Company(name="Acme", industry="retail", places=(_place("a", Source.GOOGLE_MAPS),))
    firmy = Company(name="Acme", industry="retail", places=(_place("a", Source.FIRMY_CZ),))

    assert google.places_key != firmy.places_key


def test_company_rejects_no_places() -> None:
    with pytest.raises(ValidationError):
        Company(name="Acme", industry="retail", places=())


def test_company_rejects_the_same_place_twice() -> None:
    with pytest.raises(ValidationError):
        Company(name="Acme", industry="retail", places=(_place("a"), _place("a")))


def _details(**changes: object) -> PlaceDetails:
    fields: dict[str, object] = {"rating": 4.3, "review_count": 26348}
    return PlaceDetails.model_validate(fields | changes)


def test_place_details_need_only_rating_and_review_count() -> None:
    details = _details()

    assert details.reviews_per_rating is None
    assert details.category is None
    assert details.address is None
    assert details.phone is None
    assert details.website is None
    assert details.maps_url is None
    assert details.thumbnail_url is None


def test_place_details_keep_per_star_counts_as_received_even_when_they_do_not_sum() -> None:
    details = _details(reviews_per_rating={1: 1, 2: 0, 3: 0, 4: 0, 5: 1})

    assert details.review_count == 26348
    assert details.reviews_per_rating == {1: 1, 2: 0, 3: 0, 4: 0, 5: 1}


def test_place_details_round_trip_through_json() -> None:
    details = _details(
        reviews_per_rating={1: 1752, 2: 653, 3: 1939, 4: 5468, 5: 16536},
        category="Obchod s elektronikou",
        website=None,
    )

    assert PlaceDetails.model_validate_json(details.model_dump_json()) == details


@pytest.mark.parametrize(
    "changes",
    [
        {"rating": 0.9},
        {"rating": 5.1},
        {"review_count": -1},
        {"reviews_per_rating": {6: 1}},
        {"reviews_per_rating": {1: -1}},
    ],
)
def test_place_details_reject_out_of_range_numbers(changes: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        _details(**changes)
