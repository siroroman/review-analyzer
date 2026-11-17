from datetime import UTC, datetime

import pytest

from app.domain import RunStatus, Source
from app.gateway import ClientError, ScrapedReview
from app.storage import CallFilter, UnknownRun
from tests.pipeline.helpers import (
    FIRMY,
    PLACE,
    World,
    month_of_reviews,
    with_injection,
)


def test_happy_path_ends_done_with_a_result() -> None:
    world = World(scraped_reviews=with_injection(month_of_reviews(40)))
    result = world.run()
    assert result.status is RunStatus.DONE
    assert (result.reviews, result.flagged, result.unclassified) == (42, 2, 0)
    assert result.insights == 1
    assert result.trend_points == 1
    assert world.status(result.run_id) is RunStatus.DONE
    assert result.cost == world.storage.calls.cost_by_run(CallFilter(run_id=result.run_id))[result.run_id]
    assert result.cost > 0


def test_flagged_reviews_are_stored_but_never_classified_or_shown_to_the_model() -> None:
    world = World(scraped_reviews=with_injection(month_of_reviews(40)))
    world.run()
    stored = world.storage.reviews.list_for_place(Source.GOOGLE_MAPS, PLACE.external_id)
    assert sum(r.flagged for r in stored) == 2


def test_reviews_without_text_are_stored_and_counted_but_never_sent_to_a_model() -> None:
    star_only = [
        ScrapedReview(PLACE.external_id, f"star{i}", 1, "", datetime(2026, 10, 5, 10, tzinfo=UTC), "cs")
        for i in range(3)
    ]
    world = World(scraped_reviews=[*month_of_reviews(40), *star_only])
    result = world.run()
    assert result.status is RunStatus.DONE
    assert (result.reviews, result.unclassified) == (43, 0)
    stored = world.storage.reviews.list_for_place(Source.GOOGLE_MAPS, PLACE.external_id)
    assert sum(not r.has_text for r in stored) == 3
    report = world.pipeline.report(result.run_id)
    assert report.metrics.overall is not None
    assert report.metrics.overall.count == 43
    taxonomy = world.storage.taxonomies.latest("cafe")
    assert taxonomy is not None
    topics = world.storage.reviews.topics_for_place(Source.GOOGLE_MAPS, PLACE.external_id, taxonomy)
    assert not {t.review_external_id for t in topics} & {r.external_id for r in stored if not r.has_text}


def test_budget_exceeded_while_classifying_gives_a_partial_result() -> None:
    world = World(big=frozenset({"classification"}))
    result = world.run()
    assert result.status is RunStatus.PARTIAL
    assert result.reviews == 40
    assert result.unclassified == 40
    assert result.trend_points == 1  # Metrics come from code, so the finished work still shows
    assert result.insights == 0
    assert world.model_calls_of("insights") == 0


def test_budget_exceeded_while_downloading_gives_a_partial_result_with_nothing() -> None:
    world = World(run_cap="0.0001")
    result = world.run()
    assert result.status is RunStatus.PARTIAL
    assert result.reviews == 0


def test_budget_exceeded_in_insights_keeps_reviews_topics_and_trend() -> None:
    world = World(big=frozenset({"insights"}))
    result = world.run()
    assert result.status is RunStatus.PARTIAL
    assert (result.reviews, result.unclassified, result.trend_points, result.insights) == (40, 0, 1, 0)


def test_a_step_that_keeps_failing_is_retried_and_then_ends_partial() -> None:
    world = World(always_fail={"insights": ClientError("server_error")}, max_attempts=3)
    result = world.run()
    assert result.status is RunStatus.PARTIAL
    assert world.model_calls_of("insights") == 3
    assert [d.total_seconds() for d in world.sleeper.delays] == [2, 4]


def test_a_transient_failure_is_retried_and_the_run_succeeds() -> None:
    world = World(failures={"download": [ClientError("timeout")]})
    result = world.run()
    assert result.status is RunStatus.DONE
    assert world.apify_calls() == 2


def test_a_failure_that_is_not_transient_is_not_retried() -> None:
    world = World(always_fail={"download": ClientError("schema_changed")})
    result = world.run()
    assert world.apify_calls() == 1
    assert result.status is RunStatus.FAILED  # no Review exists at all


def test_too_small_a_sample_for_a_taxonomy_ends_partial() -> None:
    world = World(scraped_reviews=month_of_reviews(5))
    result = world.run()
    assert result.status is RunStatus.PARTIAL
    assert result.reviews == 5
    assert result.unclassified == 5
    assert world.model_calls_of("taxonomy") == 0


def test_a_company_with_no_reviews_at_all_fails() -> None:
    world = World(scraped_reviews=[])
    result = world.run()
    assert result.status is RunStatus.FAILED
    assert (result.reviews, result.insights, result.trend_points) == (0, 0, 0)


def test_a_place_of_a_source_without_an_adapter_is_skipped() -> None:
    world = World(places=(PLACE, FIRMY))
    result = world.run()
    assert result.status is RunStatus.DONE
    assert world.apify_calls() == 1


def test_an_unknown_run_is_reported() -> None:
    with pytest.raises(UnknownRun):
        World().pipeline.run("nope")


def test_the_run_only_moves_forward() -> None:
    world = World()
    run_id = world.new_run()
    world.pipeline.run(run_id)
    assert world.status(run_id) is RunStatus.DONE
