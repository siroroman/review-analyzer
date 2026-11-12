import threading
from collections import deque
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal

from app.budget import Budget, BudgetConfig, BudgetExceeded, Reservation, Tokens, UnknownPrice, estimate_cost
from app.domain import Clock
from app.gateway._types import (
    CallLog,
    CallStatus,
    ClientError,
    GatewayConfig,
    GatewayDenied,
    GatewayResponse,
    ServiceCall,
    ServiceClient,
    Usage,
)

_ZERO = Decimal(0)


def _unit_of(usage: Usage) -> tuple[str, int]:
    if isinstance(usage, Tokens):
        return "token", usage.input + usage.output
    return usage.unit, usage.count


@dataclass
class _Traffic:
    """Calls admitted inside the rate window and calls in flight, of one service."""

    calls: deque[datetime] = field(default_factory=deque)
    in_flight: int = 0


class Gateway:
    """The only way to call a paid service (ADR-0006).

    Thread-safe: one lock guards the Budget (which is not thread-safe), the traffic counters and the
    Call log write, and is never held during the provider call. A Service call is written to the Call
    log before the lock is released, so the next `budget.reserve` already sees its cost in the monthly
    total (the Call log is the `MonthlySpend` of the Budget).
    """

    def __init__(
        self,
        config: GatewayConfig,
        clients: Mapping[str, ServiceClient],
        clock: Clock,
        call_log: CallLog,
    ) -> None:
        missing = sorted(set(config.services) - set(clients))
        if missing:
            raise ValueError(f"no ServiceClient for: {', '.join(missing)}")
        self._config = config
        self._clients = dict(clients)
        self._clock = clock
        self._call_log = call_log
        self._budget = Budget(BudgetConfig(config.run_cap, config.monthly_cap), call_log, clock)
        self._lock = threading.Lock()
        self._traffic = {name: _Traffic() for name in config.services}

    def call(self, service: str, operation: str, request: object, *, run_id: str) -> GatewayResponse:
        """Allow-list, limits, `budget.reserve`, the call, `budget.record`, one Service call logged.

        Raises `GatewayDenied` (not on the allow-list, unpriced, over a traffic limit) or
        `BudgetExceeded` (never retry it); the provider's `ClientError` passes through.
        """
        client = self._admit_service(service, operation, run_id)
        started = self._clock.now()
        try:
            usage = client.estimate(operation, request)
            estimate = estimate_cost(usage)
        except UnknownPrice as unknown:
            self._deny(service, operation, run_id, "unknown_price")
            raise GatewayDenied(service, operation, "unknown_price") from unknown
        with self._lock:
            traffic = self._traffic[service]
            now = self._clock.now()
            self._check_traffic(service, operation, run_id, now, started)
            try:
                reservation = self._budget.reserve(run_id, estimate)
            except BudgetExceeded:
                self._log(service, operation, run_id, "denied", _ZERO, None, started, "budget_exceeded")
                raise
            traffic.calls.append(now)
            traffic.in_flight += 1

        try:
            try:
                response = client.call(operation, request)
            except ClientError as failure:
                self._settle_failure(
                    reservation, estimate, service, operation, run_id, started, failure.kind, failure.usage
                )
                raise
            except Exception:
                self._settle_failure(
                    reservation, estimate, service, operation, run_id, started, "error", None
                )
                raise
            try:
                cost, error_kind = estimate_cost(response.usage), None
            except UnknownPrice:
                # The money is spent but cannot be priced: book the estimate, never lose the call.
                cost, error_kind = estimate, "unknown_price"
            with self._lock:
                self._budget.record(reservation, cost)
                self._log(service, operation, run_id, "ok", cost, response.usage, started, error_kind)
        finally:
            with self._lock:
                traffic.in_flight -= 1
        return GatewayResponse(response.payload, response.usage, cost)

    def _admit_service(self, service: str, operation: str, run_id: str) -> ServiceClient:
        policy = self._config.services.get(service)
        if policy is None:
            self._deny(service, operation, run_id, "service_not_allowed")
            raise GatewayDenied(service, operation, "service_not_allowed")
        if operation not in policy.operations:
            self._deny(service, operation, run_id, "operation_not_allowed")
            raise GatewayDenied(service, operation, "operation_not_allowed")
        return self._clients[service]

    def _check_traffic(
        self, service: str, operation: str, run_id: str, now: datetime, started: datetime
    ) -> None:
        """Deny at the rate or concurrency limit of the service. The caller holds the lock."""
        policy = self._config.services[service]
        traffic = self._traffic[service]
        while traffic.calls and now - traffic.calls[0] >= policy.per:
            traffic.calls.popleft()
        if len(traffic.calls) >= policy.max_calls:
            retry_after = traffic.calls[0] + policy.per - now
            self._log(service, operation, run_id, "denied", _ZERO, None, started, "rate_limited")
            raise GatewayDenied(service, operation, "rate_limited", retry_after)
        if traffic.in_flight >= policy.max_concurrent:
            self._log(service, operation, run_id, "denied", _ZERO, None, started, "concurrency_limit")
            raise GatewayDenied(service, operation, "concurrency_limit")

    def _settle_failure(
        self,
        reservation: Reservation,
        estimate: Decimal,
        service: str,
        operation: str,
        run_id: str,
        started: datetime,
        error_kind: str,
        charged: Usage | None,
    ) -> None:
        """Book what the provider charged for a failed call (nothing when unknown) and log it.

        A charge that cannot be priced is booked at the estimate and logged `unknown_price`, like an
        unpriced response: the reservation is always released and the call always logged.
        """
        cost = _ZERO
        if charged is not None:
            try:
                cost = estimate_cost(charged)
            except UnknownPrice:
                cost, error_kind = estimate, "unknown_price"
        with self._lock:
            self._budget.record(reservation, cost)
            self._log(service, operation, run_id, "failed", cost, charged, started, error_kind)

    def _deny(self, service: str, operation: str, run_id: str, reason: str) -> None:
        with self._lock:
            self._log(service, operation, run_id, "denied", _ZERO, None, self._clock.now(), reason)

    def _log(
        self,
        service: str,
        operation: str,
        run_id: str,
        status: CallStatus,
        cost: Decimal,
        usage: Usage | None,
        started: datetime,
        error_kind: str | None,
    ) -> None:
        """Write one Service call. The caller holds the lock."""
        now = self._clock.now()
        unit, units = ("", 0) if usage is None else _unit_of(usage)
        self._call_log.record(
            ServiceCall(service, operation, run_id, status, cost, unit, units, now - started, error_kind, now)
        )
