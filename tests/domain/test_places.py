import pytest
from pydantic import ValidationError

from app.domain import Company, Place, Source


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
