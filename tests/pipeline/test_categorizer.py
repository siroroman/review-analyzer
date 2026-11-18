from app.domain import RunStatus, Source
from tests.pipeline.helpers import PLACE, World, month_of_reviews, with_injection


def test_with_a_categorizer_one_model_call_gives_every_review_a_topic_and_the_run_ends_done() -> None:
    world = World(scraped_reviews=with_injection(month_of_reviews(250)), categorize=True)
    result = world.run()
    assert result.status is RunStatus.DONE
    assert (result.reviews, result.flagged, result.unclassified) == (252, 2, 0)
    assert world.model_calls_of("categorization") == 1
    assert world.model_calls_of("classification") == 0
    assert world.model_calls_of("taxonomy") == 0
    taxonomy = world.storage.taxonomies.latest("cafe")
    assert taxonomy is not None
    topics = world.storage.reviews.topics_for_place(Source.GOOGLE_MAPS, PLACE.external_id, taxonomy)
    assert len(topics) == 250


def test_the_report_names_the_topic_the_categorizer_found() -> None:
    world = World(scraped_reviews=month_of_reviews(40), categorize=True)
    report = world.pipeline.report(world.run().run_id)
    assert [t.name for t in report.topics] == ["Obsluha"]
