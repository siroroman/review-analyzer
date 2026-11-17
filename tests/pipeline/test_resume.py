from datetime import date, timedelta
from decimal import Decimal

from app.domain import Insight, InsightType, RunStatus
from tests.pipeline.helpers import World, month_of_reviews, scraped


def test_a_redelivered_finished_run_does_nothing_and_returns_the_same_result() -> None:
    world = World()
    run_id = world.new_run()
    first = world.pipeline.run(run_id)
    calls = world.service_calls()
    again = world.pipeline.run(run_id)
    assert again == first
    assert world.service_calls() == calls
    assert len(world.storage.insights.for_run(run_id)) == 1


def test_a_run_that_stopped_while_classifying_resumes_without_downloading_again() -> None:
    world = World()
    world.pipeline.run(world.new_run())  # a first Run stores and classifies everything
    stale = world.storage.runs.create(world.company.id, Decimal(5)).id
    world.clock.advance(timedelta(days=3))  # the first Run is no longer fresh
    world.storage.runs.advance(stale, RunStatus.CLASSIFYING)
    scrapes = world.scrape_calls()
    result = world.pipeline.run(stale)
    assert result.status is RunStatus.DONE
    assert world.scrape_calls() == scrapes


def test_a_run_that_stopped_while_analyzing_does_not_save_insights_twice() -> None:
    world = World()
    world.pipeline.run(world.new_run())
    world.clock.advance(timedelta(days=3))
    run_id = world.storage.runs.create(world.company.id, Decimal(5)).id
    world.storage.runs.advance(run_id, RunStatus.ANALYZING)
    world.storage.insights.save(
        run_id,
        [
            Insight(
                type=InsightType.SUMMARY,
                period_start=date(2026, 10, 1),
                period_end=date(2026, 10, 31),
                text="Hotovo.",
                review_ids=("id001",),
            )
        ],
    )
    before = world.model_calls_of("insights")
    world.pipeline.run(run_id)
    assert world.model_calls_of("insights") == before
    assert len(world.storage.insights.for_run(run_id)) == 1


def test_a_fresh_cached_company_reuses_the_result_without_any_call() -> None:
    world = World()
    first = world.run()
    calls = world.service_calls()
    world.clock.advance(timedelta(hours=1))
    second = world.run()
    assert second.status is RunStatus.DONE
    assert world.service_calls() == calls
    assert second.run_id != first.run_id
    assert (second.insights, second.trend_points, second.reviews) == (1, 1, 40)
    assert world.storage.insights.for_run(second.run_id) == world.storage.insights.for_run(first.run_id)


def test_a_stale_cache_fetches_only_new_reviews_and_classifies_only_those() -> None:
    world = World(scraped_reviews=month_of_reviews(40))
    world.run()
    world.clock.advance(timedelta(days=2))
    world.scraped = [*world.scraped, scraped(500, date(2026, 11, 10)), scraped(501, date(2026, 11, 11))]
    classified_before = world.model_calls_of("classification")
    second = world.run()
    assert second.reviews == 42
    assert world.model_calls_of("classification") == classified_before + 1  # one batch of 2 new Reviews
    assert second.unclassified == 0


def test_a_crash_after_copying_the_cached_result_leaves_a_whole_result() -> None:
    world = World()
    first = world.run()
    world.clock.advance(timedelta(hours=1))
    run_id = world.new_run()
    world.storage.runs.copy_results(first.run_id, run_id)  # the worker died before the Run became done
    before = world.service_calls()
    second = world.pipeline.run(run_id)
    assert second.status is RunStatus.DONE
    assert world.service_calls() == before
    assert (second.insights, second.trend_points) == (1, 1)


def test_a_copied_result_stays_whole_when_a_newer_run_finishes_before_the_redelivery() -> None:
    world = World()
    first = world.run()
    world.clock.advance(timedelta(hours=1))
    run_id = world.new_run()
    world.storage.runs.copy_results(first.run_id, run_id)  # the worker died before the Run became done
    world.clock.advance(timedelta(days=2))  # the cache expires ...
    world.scraped = [*world.scraped, *(scraped(600 + i, date(2026, 11, 10)) for i in range(5))]
    newer = world.run()  # ... and a newer Run finishes with its own result
    assert newer.status is RunStatus.DONE
    before = world.service_calls()
    second = world.pipeline.run(run_id)
    assert second.status is RunStatus.DONE
    assert world.service_calls() == before
    assert world.storage.insights.for_run(run_id) == world.storage.insights.for_run(first.run_id)
    assert world.storage.trends.for_run(run_id) == world.storage.trends.for_run(first.run_id)


def test_an_empty_scrape_of_a_place_that_has_stored_reviews_is_a_source_error_not_zero_new_reviews() -> None:
    world = World(scraped_reviews=month_of_reviews(40))
    world.run()
    world.clock.advance(timedelta(days=2))
    world.scraped = []  # the sidecar is blocked and answers an empty page
    second = world.run()
    assert second.status is RunStatus.PARTIAL
    assert second.reviews == 40
    assert world.scrape_calls() == 2  # a source error is not retried
