from datetime import date, timedelta
from decimal import Decimal

import pytest

from app.domain import (
    Change,
    ChangeKind,
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


def test_run_stamps_when_classifying_and_analyzing_started(storage: Storage, clock: FakeClock) -> None:
    run_id = _new_run(storage)
    queued = storage.runs.get(run_id)
    assert queued is not None
    assert (queued.classifying_at, queued.analyzing_at) == (None, None)
    storage.runs.advance(run_id, RunStatus.DOWNLOADING)
    clock.advance(timedelta(minutes=1))
    classifying_at = clock.now()
    storage.runs.advance(run_id, RunStatus.CLASSIFYING)
    clock.advance(timedelta(minutes=2))
    analyzing_at = clock.now()
    storage.runs.advance(run_id, RunStatus.ANALYZING)
    clock.advance(timedelta(minutes=1))
    done = storage.runs.advance(run_id, RunStatus.DONE)
    assert (done.classifying_at, done.analyzing_at) == (classifying_at, analyzing_at)
    assert storage.runs.get(run_id) == done


def test_a_skipped_step_has_no_start_time(storage: Storage) -> None:
    run_id = _new_run(storage)
    analyzing = storage.runs.advance(run_id, RunStatus.ANALYZING)
    assert (analyzing.classifying_at, analyzing.analyzing_at is None) == (None, False)


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


def _changes() -> list[Change]:
    return [
        Change(
            kind=ChangeKind.DROP,
            source=Source.GOOGLE_MAPS,
            period_start=date(2026, 10, 1),
            delta=-0.75,
            main_topic_key="staff",
        ),
        Change(kind=ChangeKind.RISE, source=Source.FIRMY_CZ, period_start=date(2026, 11, 1), delta=0.5),
    ]


def test_changes_come_back_in_saved_order(storage: Storage) -> None:
    run_id = _new_run(storage)
    storage.changes.save(run_id, _changes())
    assert storage.changes.for_run(run_id) == _changes()
    assert storage.changes.for_run("nope") == []


def test_results_of_an_unknown_run_are_refused(storage: Storage) -> None:
    with pytest.raises(UnknownRun):
        storage.insights.save("nope", [])
    with pytest.raises(UnknownRun):
        storage.trends.save("nope", [])
    with pytest.raises(UnknownRun):
        storage.changes.save("nope", [])


def _finished_run_with_results(storage: Storage) -> str:
    run_id = _new_run(storage)
    storage.insights.save(
        run_id,
        [
            Insight(
                type=InsightType.SUMMARY,
                period_start=date(2026, 10, 1),
                period_end=date(2026, 10, 31),
                text="Hosté chválí obsluhu.",
                review_ids=("r1",),
            )
        ],
    )
    storage.trends.save(
        run_id,
        [
            TrendPoint(
                source=Source.GOOGLE_MAPS,
                period_start=date(2026, 10, 1),
                average_rating=4.5,
                count=10,
                sentiment=0.5,
            )
        ],
    )
    storage.changes.save(run_id, _changes())
    return run_id


def test_results_are_copied_to_another_run_in_one_step(storage: Storage) -> None:
    source = _finished_run_with_results(storage)
    target = _new_run(storage)
    storage.runs.copy_results(source, target)
    assert storage.insights.for_run(target) == storage.insights.for_run(source)
    assert storage.trends.for_run(target) == storage.trends.for_run(source)
    assert storage.changes.for_run(target) == _changes()
    assert len(storage.insights.for_run(source)) == 1


def test_copying_results_twice_copies_them_once(storage: Storage) -> None:
    source = _finished_run_with_results(storage)
    target = _new_run(storage)
    storage.runs.copy_results(source, target)
    storage.runs.copy_results(source, target)
    assert len(storage.insights.for_run(target)) == 1
    assert len(storage.trends.for_run(target)) == 1
    assert len(storage.changes.for_run(target)) == 2


def test_results_are_not_copied_over_a_run_that_has_its_own(storage: Storage) -> None:
    source = _finished_run_with_results(storage)
    target = _finished_run_with_results(storage)
    storage.runs.copy_results(source, target)
    assert len(storage.insights.for_run(target)) == 1


def test_copying_results_needs_two_known_runs(storage: Storage) -> None:
    run_id = _new_run(storage)
    with pytest.raises(UnknownRun):
        storage.runs.copy_results("nope", run_id)
    with pytest.raises(UnknownRun):
        storage.runs.copy_results(run_id, "nope")


def test_a_run_has_no_industry_until_one_is_set_and_keeps_it_while_advancing(storage: Storage) -> None:
    run_id = _new_run(storage)
    assert storage.runs.get(run_id).industry is None  # type: ignore[union-attr]
    storage.runs.set_industry(run_id, "general")
    moved = storage.runs.advance(run_id, RunStatus.DOWNLOADING)
    assert moved.industry == "general"
    assert storage.runs.get(run_id) == moved


def test_setting_the_industry_of_an_unknown_run_is_refused(storage: Storage) -> None:
    with pytest.raises(UnknownRun):
        storage.runs.set_industry("nope", "cafe")


def test_copied_results_bring_the_industry_of_their_run(storage: Storage) -> None:
    source, target = _new_run(storage), _new_run(storage)
    storage.runs.set_industry(source, "general")
    storage.runs.copy_results(source, target)
    assert storage.runs.get(target).industry == "general"  # type: ignore[union-attr]
