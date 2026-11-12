from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from itertools import count
from typing import Literal, Protocol

from app.domain import Clock

_ZERO = Decimal(0)


class MonthlySpend(Protocol):
    """Repository port: what was spent on paid services in a calendar month (UTC), in USD.

    The total must include every cost already passed to `Budget.record`; the monthly cap is only as
    good as this number, and it must survive restarts (ADR-0005).
    """

    def total(self, month_start: date) -> Decimal: ...


class FakeMonthlySpend:
    """A MonthlySpend held in memory. Remembers which months were asked for."""

    def __init__(self, totals: dict[date, Decimal]) -> None:
        self._totals = dict(totals)
        self.asked: list[date] = []

    def set(self, month_start: date, total: Decimal) -> None:
        self._totals[month_start] = total

    def total(self, month_start: date) -> Decimal:
        self.asked.append(month_start)
        return self._totals.get(month_start, _ZERO)


@dataclass(frozen=True)
class BudgetConfig:
    """Caps in USD, read from configuration."""

    run_cap: Decimal
    monthly_cap: Decimal = Decimal(30)

    def __post_init__(self) -> None:
        if self.run_cap <= _ZERO or self.monthly_cap <= _ZERO:
            raise ValueError("a cap must be positive")


class BudgetExceeded(Exception):  # noqa: N818 - the name is fixed by the specification and ADR-0006
    """A paid call would break a cap. Never retried (ADR-0005)."""

    def __init__(self, cap_kind: Literal["run", "monthly"], cap: Decimal, needed: Decimal) -> None:
        super().__init__(f"{cap_kind} cap {cap} USD would be exceeded: {needed} USD needed")
        self.cap_kind = cap_kind
        self.cap = cap
        self.needed = needed


@dataclass(frozen=True)
class Reservation:
    """Money held for one paid call until `Budget.record` settles it."""

    id: int
    run_id: str
    amount: Decimal


class Budget:
    """Cap per Run and monthly cap over every paid service. Single process, not thread-safe."""

    def __init__(self, config: BudgetConfig, monthly_spend: MonthlySpend, clock: Clock) -> None:
        self._config = config
        self._monthly_spend = monthly_spend
        self._clock = clock
        self._ids = count(1)
        self._open: dict[int, Reservation] = {}
        self._run_spent: dict[str, Decimal] = {}

    def reserve(self, run_id: str, estimate: Decimal) -> Reservation:
        """Hold `estimate` USD for a call, or raise `BudgetExceeded`. Exactly at a cap is allowed."""
        if estimate <= _ZERO:
            raise ValueError("estimate must be positive")

        month_needed = self._monthly_total() + self._in_flight() + estimate
        if month_needed > self._config.monthly_cap:
            raise BudgetExceeded("monthly", self._config.monthly_cap, month_needed)

        run_needed = self._run_spent.get(run_id, _ZERO) + self._in_flight(run_id) + estimate
        if run_needed > self._config.run_cap:
            raise BudgetExceeded("run", self._config.run_cap, run_needed)

        reservation = Reservation(next(self._ids), run_id, estimate)
        self._open[reservation.id] = reservation
        return reservation

    def record(self, reservation: Reservation, cost: Decimal) -> None:
        """Settle a reservation with the real cost, which may be above or below the estimate.

        The cost is always booked, even when it breaks a cap: the money is spent. Later reserves see it.
        A failed call is recorded with a cost of zero.
        """
        if cost < _ZERO:
            raise ValueError("cost must not be negative")
        if reservation.id not in self._open:
            raise ValueError("unknown or already recorded reservation")
        del self._open[reservation.id]
        self._run_spent[reservation.run_id] = self._run_spent.get(reservation.run_id, _ZERO) + cost

    def _monthly_total(self) -> Decimal:
        now = self._clock.now()
        return self._monthly_spend.total(date(now.year, now.month, 1))

    def _in_flight(self, run_id: str | None = None) -> Decimal:
        return sum(
            (r.amount for r in self._open.values() if run_id is None or r.run_id == run_id),
            _ZERO,
        )
