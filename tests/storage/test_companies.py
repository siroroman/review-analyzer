import pytest

from app.domain import Company, Source
from app.storage import Storage, StoredCompany
from tests.storage.helpers import company, place


def company_without_industry() -> Company:
    return Company(name="Kavárna", places=(place("g1"),))


def test_same_set_of_places_is_the_same_company_in_any_order(storage: Storage) -> None:
    a, b = place("g1"), place("g2")
    first = storage.companies.get_or_create(company(a, b, name="First"))
    second = storage.companies.get_or_create(company(b, a, name="Second"))
    assert second.id == first.id
    assert second.company.name == "First"
    assert [p.external_id for p in second.company.places] == ["g1", "g2"]


def test_different_set_is_a_different_company(storage: Storage) -> None:
    first = storage.companies.get_or_create(company(place("g1")))
    second = storage.companies.get_or_create(company(place("g1"), place("g2")))
    assert second.id != first.id


def test_get_finds_by_places_key_and_misses_unknown(storage: Storage) -> None:
    stored = storage.companies.get_or_create(company())
    assert storage.companies.get(company().places_key) == stored
    assert storage.companies.get("nope") is None


def test_one_place_belongs_to_several_companies(storage: Storage) -> None:
    solo = storage.companies.get_or_create(company(place("g1")))
    chain = storage.companies.get_or_create(company(place("g1"), place("g2")))
    found = storage.companies.containing(Source.GOOGLE_MAPS, "g1")
    assert [c.id for c in found] == [solo.id, chain.id]
    assert storage.companies.containing(Source.FIRMY_CZ, "g1") == []


def test_a_place_seen_again_takes_the_newest_name(storage: Storage) -> None:
    storage.companies.get_or_create(company(place("g1", name="Old")))
    storage.companies.get_or_create(company(place("g1", name="New"), place("g2")))
    [solo, chain] = storage.companies.containing(Source.GOOGLE_MAPS, "g1")
    assert solo.company.places[0].name == "New"
    assert chain.company.places[0].name == "New"


def test_by_id_finds_the_stored_company_and_misses_unknown(storage: Storage) -> None:
    stored = storage.companies.get_or_create(company(place("g1"), place("g2")))
    assert storage.companies.by_id(stored.id) == stored
    assert storage.companies.by_id(stored.id + 100) is None


def test_a_company_has_no_industry_until_one_is_set(storage: Storage) -> None:
    stored = storage.companies.get_or_create(Company(name="Kavárna", places=(place("g1"),)))
    assert stored.company.industry is None


def test_set_industry_is_kept_for_the_same_set_of_places(storage: Storage) -> None:
    stored = storage.companies.get_or_create(company_without_industry())
    storage.companies.set_industry(stored.id, "cafe")
    again = storage.companies.get_or_create(company_without_industry())
    assert again.id == stored.id
    assert again.company.industry == "cafe"
    assert storage.companies.by_id(stored.id) == again


def test_set_industry_replaces_the_previous_one(storage: Storage) -> None:
    stored = storage.companies.get_or_create(company_without_industry())
    storage.companies.set_industry(stored.id, "general")
    storage.companies.set_industry(stored.id, "cafe")
    assert storage.companies.by_id(stored.id) == StoredCompany(
        stored.id, stored.company.model_copy(update={"industry": "cafe"})
    )


def test_set_industry_of_an_unknown_company_is_an_error(storage: Storage) -> None:
    with pytest.raises(LookupError):
        storage.companies.set_industry(999, "cafe")
