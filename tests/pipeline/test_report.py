from datetime import date

import pytest

from app.domain import DatePrecision, Review, RunStatus, Source
from app.metrics import compute
from app.storage import UnknownRun
from tests.pipeline.helpers import PLACE, World, scraped


def test_a_report_holds_the_result_the_company_and_what_the_run_saved() -> None:
    world = World()
    result = world.run()
    report = world.pipeline.report(result.run_id)
    assert report.result == result
    assert report.company.name == world.company.company.name
    assert report.status is RunStatus.DONE
    assert list(report.insights) == world.storage.insights.for_run(result.run_id)
    assert report.metrics.overall is not None
    assert report.metrics.overall.count == 40


def test_the_trend_of_a_report_is_the_one_the_run_saved_not_a_new_one() -> None:
    world = World()
    result = world.run()
    saved = world.storage.trends.for_run(result.run_id)
    world.storage.reviews.add(
        [
            Review(
                source=Source.GOOGLE_MAPS,
                place_external_id=PLACE.external_id,
                external_id="later",
                rating=1,
                text="a later Review",
                published_on=date(2026, 12, 2),
                date_precision=DatePrecision.DAY,
                language="cs",
                text_hash="later-hash",
                flagged=False,
            )
        ]
    )
    report = world.pipeline.report(result.run_id)
    assert list(report.metrics.trend) == saved
    assert len(saved) == 1


def test_a_report_of_an_unknown_run_raises() -> None:
    with pytest.raises(UnknownRun):
        World().pipeline.report("nope")


def test_a_report_does_not_show_changes_that_only_later_reviews_would_make() -> None:
    first = [scraped(i, date(2026, 9, 1 + i)) for i in range(10)]
    second = [scraped(10 + i, date(2026, 10, 1 + i)) for i in range(10)]
    world = World(scraped_reviews=first + second)
    result = world.run()
    world.storage.reviews.add(
        [
            Review(
                source=Source.GOOGLE_MAPS,
                place_external_id=PLACE.external_id,
                external_id=f"bad-{index}",
                rating=1,
                text=f"bad {index}",
                published_on=date(2026, 10, 25),
                date_precision=DatePrecision.DAY,
                language="cs",
                text_hash=f"bad-hash-{index}",
                flagged=False,
            )
            for index in range(10)
        ]
    )
    stored = world.storage.reviews.list_for_place(Source.GOOGLE_MAPS, PLACE.external_id)
    assert compute(stored, []).changes  # today's Reviews do show a drop in October ...
    report = world.pipeline.report(result.run_id)
    assert report.metrics.changes == ()  # ... and the report, tied to the Run's trend, does not
    assert [point.period_start for point in report.metrics.trend] == [date(2026, 9, 1), date(2026, 10, 1)]


def _drop_and_rise_world() -> World:
    september = [scraped(i, date(2026, 9, 1 + i), rating=5) for i in range(10)]
    october = [scraped(10 + i, date(2026, 10, 1 + i), "Špatná obsluha", rating=2) for i in range(10)]
    november = [scraped(20 + i, date(2026, 11, 1 + i), rating=5) for i in range(10)]
    return World(scraped_reviews=september + october + november)


def test_a_report_carries_the_drops_and_rises_the_run_saved_with_the_main_topic_of_a_drop() -> None:
    world = _drop_and_rise_world()
    result = world.run()
    report = world.pipeline.report(result.run_id)
    assert [(c.kind.value, c.period_start, c.delta, c.main_topic_key) for c in report.metrics.changes] == [
        ("drop", date(2026, 10, 1), -3.0, "staff"),
        ("rise", date(2026, 11, 1), 3.0, "staff"),
    ]


def test_the_changes_of_a_report_are_the_ones_the_run_saved_not_new_ones() -> None:
    world = _drop_and_rise_world()
    result = world.run()
    saved = world.storage.changes.for_run(result.run_id)
    world.storage.reviews.add(
        [
            Review(
                source=Source.GOOGLE_MAPS,
                place_external_id=PLACE.external_id,
                external_id=f"later-{index}",
                rating=1,
                text=f"later {index}",
                published_on=date(2026, 11, 20),
                date_precision=DatePrecision.DAY,
                language="cs",
                text_hash=f"later-hash-{index}",
                flagged=False,
            )
            for index in range(20)
        ]
    )
    assert list(world.pipeline.report(result.run_id).metrics.changes) == saved
    assert len(saved) == 2


def test_a_run_that_reuses_a_fresh_run_reports_the_same_changes() -> None:
    world = _drop_and_rise_world()
    first = world.run()
    second = world.run()
    assert second.run_id != first.run_id
    assert (
        world.pipeline.report(second.run_id).metrics.changes
        == world.pipeline.report(first.run_id).metrics.changes
    )
    assert len(world.pipeline.report(second.run_id).metrics.changes) == 2


def test_a_report_names_every_topic_it_mentions() -> None:
    world = _drop_and_rise_world()
    result = world.run()
    report = world.pipeline.report(result.run_id)
    assert [(t.key, t.name) for t in report.topics] == [("staff", "Staff")]


def test_a_report_has_no_topic_names_before_any_review_is_classified() -> None:
    world = World()
    assert world.pipeline.report(world.new_run()).topics == ()
