from datetime import date

import pytest

from app.domain import ReviewTopic, Sentiment, Source, Taxonomy, Topic
from app.storage import Storage, UnknownPlace
from tests.storage.helpers import company, place, review


def _topic(review_external_id: str, key: str = "staff") -> ReviewTopic:
    return ReviewTopic(
        review_external_id=review_external_id, topic_key=key, sentiment=Sentiment.NEGATIVE, confidence=0.9
    )


def test_reviews_round_trip_oldest_first(storage: Storage) -> None:
    storage.companies.get_or_create(company())
    later = review("r2", published_on=date(2026, 10, 5))
    earlier = review("r1", published_on=date(2026, 10, 1))
    assert storage.reviews.add([later, earlier]) == 2
    assert storage.reviews.list_for_place(Source.GOOGLE_MAPS, "g1") == [earlier, later]


def test_source_and_external_id_is_unique(storage: Storage) -> None:
    storage.companies.get_or_create(company(place("g1"), place("f1", Source.FIRMY_CZ)))
    assert storage.reviews.add([review("r1")]) == 1
    assert storage.reviews.add([review("r1"), review("r2")]) == 1
    # the same external ID on another Source is another Review
    assert storage.reviews.add([review("r1", "f1", Source.FIRMY_CZ)]) == 1
    assert len(storage.reviews.list_for_place(Source.GOOGLE_MAPS, "g1")) == 2


def test_duplicate_inside_one_batch_is_stored_once(storage: Storage) -> None:
    storage.companies.get_or_create(company())
    assert storage.reviews.add([review("r1"), review("r1")]) == 1


def test_review_of_an_unknown_place_is_refused_and_nothing_is_stored(storage: Storage) -> None:
    storage.companies.get_or_create(company())
    with pytest.raises(UnknownPlace):
        storage.reviews.add([review("r1"), review("r2", "elsewhere")])
    assert storage.reviews.list_for_place(Source.GOOGLE_MAPS, "g1") == []


def test_unclassified_follows_the_taxonomy_version_and_skips_flagged(storage: Storage) -> None:
    storage.companies.get_or_create(company())
    storage.reviews.add([review("r1"), review("r2"), review("r3", flagged=True)])
    v1 = storage.taxonomies.save(
        Taxonomy(industry="cafe", topics=(Topic(key="staff", name="Staff", description=""),))
    )
    assert [r.external_id for r in storage.reviews.unclassified(Source.GOOGLE_MAPS, "g1", v1)] == ["r1", "r2"]

    storage.reviews.save_topics(Source.GOOGLE_MAPS, v1, [_topic("r1")])
    assert [r.external_id for r in storage.reviews.unclassified(Source.GOOGLE_MAPS, "g1", v1)] == ["r2"]

    v2 = storage.taxonomies.save(
        Taxonomy(industry="cafe", topics=(Topic(key="price", name="Price", description=""),))
    )
    assert [r.external_id for r in storage.reviews.unclassified(Source.GOOGLE_MAPS, "g1", v2)] == ["r1", "r2"]


def test_topics_are_kept_per_version_and_a_repeat_replaces(storage: Storage) -> None:
    storage.companies.get_or_create(company())
    storage.reviews.add([review("r1")])
    v1 = storage.taxonomies.save(
        Taxonomy(industry="cafe", topics=(Topic(key="staff", name="Staff", description=""),))
    )
    storage.reviews.save_topics(Source.GOOGLE_MAPS, v1, [_topic("r1")])
    better = ReviewTopic(
        review_external_id="r1", topic_key="staff", sentiment=Sentiment.POSITIVE, confidence=0.5
    )
    storage.reviews.save_topics(Source.GOOGLE_MAPS, v1, [better])
    assert storage.reviews.topics_for_place(Source.GOOGLE_MAPS, "g1", v1) == [better]


def test_topics_of_a_review_that_is_not_stored_are_refused(storage: Storage) -> None:
    storage.companies.get_or_create(company())
    v1 = storage.taxonomies.save(
        Taxonomy(industry="cafe", topics=(Topic(key="staff", name="Staff", description=""),))
    )
    with pytest.raises(LookupError):
        storage.reviews.save_topics(Source.GOOGLE_MAPS, v1, [_topic("ghost")])
