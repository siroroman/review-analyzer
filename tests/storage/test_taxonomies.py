from app.domain import Taxonomy, Topic
from app.storage import Storage


def _taxonomy(industry: str, key: str) -> Taxonomy:
    return Taxonomy(industry=industry, topics=(Topic(key=key, name=key.title(), description="d"),))


def test_every_save_is_a_new_version_and_old_ones_stay(storage: Storage) -> None:
    v1 = storage.taxonomies.save(_taxonomy("cafe", "staff"))
    v2 = storage.taxonomies.save(_taxonomy("cafe", "price"))
    assert (v1.version, v2.version) == (1, 2)
    assert storage.taxonomies.get("cafe", 1) == v1
    assert storage.taxonomies.latest("cafe") == v2
    assert v1.taxonomy.topics[0].key == "staff"


def test_versions_count_per_industry(storage: Storage) -> None:
    storage.taxonomies.save(_taxonomy("cafe", "staff"))
    assert storage.taxonomies.save(_taxonomy("gym", "staff")).version == 1


def test_unknown_taxonomy_is_none(storage: Storage) -> None:
    assert storage.taxonomies.latest("cafe") is None
    assert storage.taxonomies.get("cafe", 3) is None
