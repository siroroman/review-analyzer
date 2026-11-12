from datetime import date, timedelta
from decimal import Decimal

import pytest

from app.domain import (
    FakeClock,
    Insight,
    InsightType,
    InvalidTransition,
    RunStatus,
    Source,
    TrendPoint,
)
from app.storage import Storage, UnknownRun
from tests.storage.helpers import company

TTL = timedelta(hours=24)


def _new_run(storage: Storage) -> str:
    stored = storage.companies.get_or_create(company())
    return storage.runs.create(stored.id, Decimal("2.5")).id


def test_a_new_run_is_queued_with_its_budget_cap(storage: Storage, clock: FakeClock) -> None:
    stored = storage.companies.get_or_create(company())
    run = storage.runs.create(stored.id, Decimal("2.5"))
    assert (run.status, run.budget_cap, run.company_id) == (RunStatus.QUEUED, Decimal("2.5"), stored.id)
    assert (run.created_at, run.finished_at) == (clock.now(), None)
    assert storage.runs.get(run.id) == run
    assert storage.runs.get("nope") is None


def test_a_run_for_an_unknown_company_is_refused(storage: Storage) -> None:
    with pytest.raises(LookupError):
        storage.runs.create(999, Decimal(1))


def test_run_moves_forward_and_final_status_stamps_the_time(storage: Storage, clock: FakeClock) -> None:
    run_id = _new_run(storage)
    assert storage.runs.advance(run_id, RunStatus.DOWNLOADING).finished_at is None
    clock.advance(timedelta(minutes=3))
    done = storage.runs.advance(run_id, RunStatus.DONE)
    assert (done.status, done.finished_at) == (RunStatus.DONE, clock.now())
    assert storage.runs.get(run_id) == done


def test_run_cannot_go_back_or_leave_a_final_status(storage: Storage) -> None:
    run_id = _new_run(storage)
    storage.runs.advance(run_id, RunStatus.CLASSIFYING)
    with pytest.raises(InvalidTransition):
        storage.runs.advance(run_id, RunStatus.DOWNLOADING)
    storage.runs.advance(run_id, RunStatus.FAILED)
    with pytest.raises(InvalidTransition):
        storage.runs.advance(run_id, RunStatus.DONE)
    failed = storage.runs.get(run_id)
    assert failed is not None
    assert failed.status is RunStatus.FAILED


def test_advancing_an_unknown_run_is_refused(storage: Storage) -> None:
    with pytest.raises(UnknownRun):
        storage.runs.advance("nope", RunStatus.DONE)


def test_cache_returns_the_newest_done_run_while_it_is_fresh(storage: Storage, clock: FakeClock) -> None:
    stored = storage.companies.get_or_create(company())
    assert storage.runs.fresh_for(stored.id, TTL) is None

    old = storage.runs.create(stored.id, Decimal(1))
    storage.runs.advance(old.id, RunStatus.DONE)
    clock.advance(timedelta(hours=1))
    newer = storage.runs.create(stored.id, Decimal(1))
    done = storage.runs.advance(newer.id, RunStatus.DONE)
    clock.advance(timedelta(hours=1))

    assert storage.runs.fresh_for(stored.id, TTL) == done


def test_cache_expires_exactly_at_the_ttl(storage: Storage, clock: FakeClock) -> None:
    stored = storage.companies.get_or_create(company())
    run = storage.runs.create(stored.id, Decimal(1))
    storage.runs.advance(run.id, RunStatus.DONE)
    clock.advance(TTL - timedelta(seconds=1))
    assert storage.runs.fresh_for(stored.id, TTL) is not None
    clock.advance(timedelta(seconds=1))
    assert storage.runs.fresh_for(stored.id, TTL) is None


def test_cache_ignores_unfinished_partial_failed_and_other_companies(storage: Storage) -> None:
    stored = storage.companies.get_or_create(company())
    other = storage.companies.get_or_create(company(name="Other"))  # same places: same Company
    assert other.id == stored.id
    for final in (RunStatus.PARTIAL, RunStatus.FAILED):
        storage.runs.advance(storage.runs.create(stored.id, Decimal(1)).id, final)
    storage.runs.create(stored.id, Decimal(1))
    assert storage.runs.fresh_for(stored.id, TTL) is None


def test_insights_and_trend_points_come_back_in_saved_order(storage: Storage) -> None:
    run_id = _new_run(storage)
    insights = [
        Insight(
            type=InsightType.SUMMARY,
            period_start=date(2026, 10, 1),
            period_end=date(2026, 10, 31),
            text="Rating fell.",
            review_ids=("r1", "r2"),
        ),
        Insight(
            type=InsightType.SUGGESTION,
            period_start=date(2026, 10, 1),
            period_end=date(2026, 10, 31),
            text="Hire staff.",
            review_ids=("r2",),
        ),
    ]
    points = [
        TrendPoint(
            source=Source.GOOGLE_MAPS,
            period_start=date(2026, m, 1),
            average_rating=4.25,
            count=8,
            sentiment=0.1,
        )
        for m in (9, 10)
    ]
    storage.insights.save(run_id, insights)
    storage.trends.save(run_id, points)
    assert storage.insights.for_run(run_id) == insights
    assert storage.trends.for_run(run_id) == points
    assert storage.insights.for_run("nope") == []


def test_results_of_an_unknown_run_are_refused(storage: Storage) -> None:
    with pytest.raises(UnknownRun):
        storage.insights.save("nope", [])
    with pytest.raises(UnknownRun):
        storage.trends.save("nope", [])
