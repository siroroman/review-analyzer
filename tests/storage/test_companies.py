from app.domain import Source
from app.storage import Storage
from tests.storage.helpers import company, place


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
