from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest
from hypothesis import given
from hypothesis import strategies as st

from app.budget import Budget, BudgetConfig, BudgetExceeded, FakeMonthlySpend
from app.domain import FakeClock

D = Decimal


def make(
    run_cap: str = "5",
    monthly_cap: str = "30",
    month_total: str = "0",
) -> tuple[Budget, FakeMonthlySpend, FakeClock]:
    clock = FakeClock(datetime(2026, 11, 12, 8, 0, tzinfo=UTC))
    spend = FakeMonthlySpend({date(2026, 11, 1): D(month_total)})
    budget = Budget(BudgetConfig(run_cap=D(run_cap), monthly_cap=D(monthly_cap)), spend, clock)
    return budget, spend, clock


def test_monthly_cap_defaults_to_30_usd() -> None:
    assert BudgetConfig(run_cap=D(5)).monthly_cap == D(30)


@pytest.mark.parametrize("bad", ["0", "-1"])
def test_a_cap_must_be_positive(bad: str) -> None:
    with pytest.raises(ValueError, match="cap"):
        BudgetConfig(run_cap=D(bad))
    with pytest.raises(ValueError, match="cap"):
        BudgetConfig(run_cap=D(5), monthly_cap=D(bad))


def test_reserve_within_the_caps_returns_a_reservation() -> None:
    budget, _, _ = make()

    reservation = budget.reserve("run-1", D("1.5"))

    assert reservation.run_id == "run-1"
    assert reservation.amount == D("1.5")


def test_reserve_at_exactly_the_run_cap_is_allowed() -> None:
    budget, _, _ = make(run_cap="5")

    budget.reserve("run-1", D(5))


def test_reserve_one_cent_above_the_run_cap_is_refused() -> None:
    budget, _, _ = make(run_cap="5")

    with pytest.raises(BudgetExceeded) as info:
        budget.reserve("run-1", D("5.01"))

    assert info.value.cap_kind == "run"
    assert info.value.cap == D(5)
    assert info.value.needed == D("5.01")


def test_the_run_cap_counts_recorded_cost_of_the_same_run() -> None:
    budget, _, _ = make(run_cap="5")
    budget.record(budget.reserve("run-1", D(3)), D(3))

    with pytest.raises(BudgetExceeded) as info:
        budget.reserve("run-1", D("2.01"))

    assert info.value.needed == D("5.01")
    budget.reserve("run-1", D(2))


def test_the_run_cap_counts_calls_still_in_flight() -> None:
    budget, _, _ = make(run_cap="5")
    budget.reserve("run-1", D(3))

    with pytest.raises(BudgetExceeded):
        budget.reserve("run-1", D("2.01"))


def test_another_run_has_its_own_run_cap() -> None:
    budget, _, _ = make(run_cap="5")
    budget.reserve("run-1", D(5))

    budget.reserve("run-2", D(5))


def test_a_cost_above_the_estimate_is_recorded_and_eats_the_rest_of_the_cap() -> None:
    budget, _, _ = make(run_cap="5")
    budget.record(budget.reserve("run-1", D(1)), D(4))  # real cost 4x the estimate

    budget.reserve("run-1", D(1))  # 4 + 1 = 5, exactly the cap
    with pytest.raises(BudgetExceeded):
        budget.reserve("run-1", D("0.01"))


def test_a_cost_below_the_estimate_frees_the_difference() -> None:
    budget, _, _ = make(run_cap="5")
    budget.record(budget.reserve("run-1", D(5)), D("0.5"))

    budget.reserve("run-1", D("4.5"))


def test_a_failed_call_recorded_at_zero_releases_the_reservation() -> None:
    budget, _, _ = make(run_cap="5")
    budget.record(budget.reserve("run-1", D(5)), D(0))

    budget.reserve("run-1", D(5))


@pytest.mark.parametrize("estimate", ["0", "-0.01", "-5"])
def test_a_zero_or_negative_estimate_is_rejected(estimate: str) -> None:
    budget, _, _ = make()

    with pytest.raises(ValueError, match="estimate"):
        budget.reserve("run-1", D(estimate))


def test_a_rejected_estimate_reserves_nothing() -> None:
    budget, _, _ = make(run_cap="5")
    with pytest.raises(ValueError, match="estimate"):
        budget.reserve("run-1", D(-5))

    budget.reserve("run-1", D(5))


def test_a_negative_cost_is_rejected() -> None:
    budget, _, _ = make()
    reservation = budget.reserve("run-1", D(1))

    with pytest.raises(ValueError, match="cost"):
        budget.record(reservation, D(-1))


def test_a_reservation_is_recorded_once() -> None:
    budget, _, _ = make()
    reservation = budget.reserve("run-1", D(1))
    budget.record(reservation, D(1))

    with pytest.raises(ValueError, match="reservation"):
        budget.record(reservation, D(1))


def test_the_monthly_total_comes_from_the_repository() -> None:
    budget, spend, _ = make(run_cap="100", monthly_cap="30", month_total="29")

    budget.reserve("run-1", D(1))  # exactly 30
    with pytest.raises(BudgetExceeded) as info:
        budget.reserve("run-2", D("0.01"))

    assert info.value.cap_kind == "monthly"
    assert info.value.cap == D(30)
    assert info.value.needed == D("30.01")
    assert set(spend.asked) == {date(2026, 11, 1)}


def test_monthly_cap_wins_when_both_caps_are_exceeded() -> None:
    budget, _, _ = make(run_cap="1", monthly_cap="30", month_total="30")

    with pytest.raises(BudgetExceeded) as info:
        budget.reserve("run-1", D(2))

    assert info.value.cap_kind == "monthly"


def test_the_monthly_cap_counts_in_flight_calls_of_other_runs() -> None:
    budget, _, _ = make(run_cap="100", month_total="28")
    budget.reserve("run-1", D(2))

    with pytest.raises(BudgetExceeded):
        budget.reserve("run-2", D("0.01"))


def test_a_new_month_starts_from_that_months_total() -> None:
    budget, spend, clock = make(run_cap="100", month_total="30")
    spend.set(date(2026, 12, 1), D(0))
    clock.advance(timedelta(days=20))

    budget.reserve("run-1", D(10))

    assert spend.asked == [date(2026, 12, 1)]


def test_an_empty_month_has_nothing_spent() -> None:
    clock = FakeClock(datetime(2027, 1, 31, 23, 59, tzinfo=UTC))
    budget = Budget(BudgetConfig(run_cap=D(30)), FakeMonthlySpend({}), clock)

    budget.reserve("run-1", D(30))


@given(
    run_cap=st.decimals(min_value="0.01", max_value="100", places=2),
    estimates=st.lists(st.decimals(min_value="0.01", max_value="50", places=2), max_size=20),
)
def test_reserved_money_of_a_run_never_exceeds_its_cap(run_cap: Decimal, estimates: list[Decimal]) -> None:
    budget, _, _ = make(run_cap=str(run_cap), monthly_cap="100000")
    granted = D(0)

    for estimate in estimates:
        try:
            budget.reserve("run-1", estimate)
        except BudgetExceeded:
            continue
        granted += estimate

    assert granted <= run_cap
