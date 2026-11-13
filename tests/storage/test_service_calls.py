from datetime import UTC, date, datetime, timedelta, timezone
from decimal import Decimal

from app.gateway import ServiceCall
from app.storage import CallFilter, Storage
from tests.storage.helpers import START, call

D = Decimal


def _fill(storage: Storage) -> list[ServiceCall]:
    calls = [
        call("apify", "run_actor", "run-1", "ok", "1.25", START),
        call("anthropic", "complete", "run-1", "ok", "0.5", START + timedelta(hours=1)),
        call("anthropic", "complete", "run-2", "failed", "0.25", START + timedelta(days=1)),
        call("google_places", "details", "run-2", "denied", "0", START + timedelta(days=1, hours=2)),
        call("apify", "run_actor", "run-3", "ok", "2", START + timedelta(days=40)),
    ]
    for c in calls:
        storage.calls.record(c)
    return calls


def test_a_call_round_trips_exactly(storage: Storage) -> None:
    original = call(cost="0.017", at=datetime(2026, 11, 12, 23, 59, 59, 999_999, tzinfo=UTC))
    storage.calls.record(original)
    [back] = storage.calls.query(CallFilter())
    assert back == original


def test_query_without_a_filter_returns_everything_oldest_first(storage: Storage) -> None:
    calls = _fill(storage)
    assert storage.calls.query(CallFilter()) == calls


def test_query_filters_by_each_field(storage: Storage) -> None:
    calls = _fill(storage)
    assert storage.calls.query(CallFilter(service="apify")) == [calls[0], calls[4]]
    assert storage.calls.query(CallFilter(operation="details")) == [calls[3]]
    assert storage.calls.query(CallFilter(run_id="run-1")) == calls[:2]
    assert storage.calls.query(CallFilter(status="failed")) == [calls[2]]


def test_query_date_range_includes_since_and_excludes_until(storage: Storage) -> None:
    calls = _fill(storage)
    one = START + timedelta(hours=1)
    assert storage.calls.query(CallFilter(since=one, until=START + timedelta(days=1))) == [calls[1]]
    assert storage.calls.query(CallFilter(until=START)) == []


def test_filters_combine(storage: Storage) -> None:
    calls = _fill(storage)
    assert storage.calls.query(CallFilter(service="anthropic", run_id="run-2")) == [calls[2]]
    assert storage.calls.query(CallFilter(service="apify", status="failed")) == []


def test_monthly_total_is_the_utc_calendar_month(storage: Storage) -> None:
    _fill(storage)
    storage.calls.record(call(cost="9", at=datetime(2026, 11, 30, 23, 59, tzinfo=UTC)))
    storage.calls.record(call(cost="100", at=datetime(2026, 12, 1, 0, 0, tzinfo=UTC)))
    assert storage.calls.total(date(2026, 11, 1)) == D("11.0")
    assert storage.calls.total(date(2026, 12, 1)) > D(100)
    assert storage.calls.total(date(2026, 1, 1)) == D(0)


def test_sums_per_service_day_and_run(storage: Storage) -> None:
    _fill(storage)
    everything = CallFilter()
    assert storage.calls.cost_by_service(everything) == {
        "apify": D("3.25"),
        "anthropic": D("0.75"),
        "google_places": D(0),
    }
    assert storage.calls.cost_by_day(everything) == {
        date(2026, 11, 12): D("1.75"),
        date(2026, 11, 13): D("0.25"),
        date(2026, 12, 22): D(2),
    }
    assert storage.calls.cost_by_run(everything) == {"run-1": D("1.75"), "run-2": D("0.25"), "run-3": D(2)}


def test_sums_respect_the_filter_and_an_empty_match_is_empty(storage: Storage) -> None:
    _fill(storage)
    assert storage.calls.cost_by_service(CallFilter(run_id="run-1")) == {
        "apify": D("1.25"),
        "anthropic": D("0.5"),
    }
    assert storage.calls.cost_by_run(CallFilter(service="nobody")) == {}
    assert storage.calls.cost_by_day(CallFilter(service="nobody")) == {}


def test_the_day_is_the_utc_day_whatever_the_zone_of_the_call(storage: Storage) -> None:
    prague = timezone(timedelta(hours=1))
    storage.calls.record(call(cost="1", at=datetime(2026, 11, 13, 0, 30, tzinfo=prague)))
    assert storage.calls.cost_by_day(CallFilter()) == {date(2026, 11, 12): D(1)}
