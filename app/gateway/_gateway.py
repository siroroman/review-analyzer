import threading
from collections.abc import Mapping
from datetime import datetime
from decimal import Decimal

from app.budget import Budget, BudgetConfig, BudgetExceeded, Tokens, UnknownPrice, estimate_cost
from app.domain import Clock
from app.gateway._types import (
    CallLog,
    CallStatus,
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
            try:
                reservation = self._budget.reserve(run_id, estimate)
            except BudgetExceeded:
                self._log(service, operation, run_id, "denied", _ZERO, None, started, "budget_exceeded")
                raise

        response = client.call(operation, request)
        cost = estimate_cost(response.usage)
        with self._lock:
            self._budget.record(reservation, cost)
            self._log(service, operation, run_id, "ok", cost, response.usage, started, None)
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
