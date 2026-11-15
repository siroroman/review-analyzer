from datetime import date

import pytest

from app.domain import DatePrecision, Review, RunStatus, Source
from app.storage import UnknownRun
from tests.pipeline.helpers import PLACE, World


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
