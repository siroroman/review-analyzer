from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Literal, Protocol

from app.budget import Tokens, Units

Usage = Tokens | Units
CallStatus = Literal["ok", "denied", "failed"]
DeniedReason = Literal[
    "service_not_allowed",
    "operation_not_allowed",
    "unknown_price",
    "rate_limited",
    "concurrency_limit",
]


@dataclass(frozen=True)
class ClientResponse:
    """What a ServiceClient returns: the provider's answer and what it actually used."""

    payload: object
    usage: Usage


@dataclass(frozen=True)
class GatewayResponse:
    """What `Gateway.call` returns: the answer, the actual usage and its cost in USD."""

    payload: object
    usage: Usage
    cost: Decimal


class ClientError(Exception):
    """A paid call failed. `kind` is a short machine word, never part of a request or response.

    `usage` is what the provider already charged for the failed call; `None` means nothing was charged.
    """

    def __init__(self, kind: str, usage: Usage | None = None) -> None:
        super().__init__(kind)
        self.kind = kind
        self.usage = usage


class ClientTimeout(ClientError):
    """The provider did not answer in time."""

    def __init__(self, usage: Usage | None = None) -> None:
        super().__init__("timeout", usage)


class GatewayDenied(Exception):
    """The call was not made. Retry only for `rate_limited` and `concurrency_limit`, never otherwise."""

    def __init__(
        self,
        service: str,
        operation: str,
        reason: DeniedReason,
        retry_after: timedelta | None = None,
    ) -> None:
        super().__init__(f"{service}/{operation} denied: {reason}")
        self.service = service
        self.operation = operation
        self.reason = reason
        self.retry_after = retry_after


class ServiceClient(Protocol):
    """Port: one paid service (adapter of OpenRouter, Anthropic, Apify, Google Places)."""

    def estimate(self, operation: str, request: object) -> Usage:
        """The usage the call is expected to need, for the Budget check before it."""
        ...

    def call(self, operation: str, request: object) -> ClientResponse:
        """Make the call. Raises `ClientError` (or a subclass) on failure."""
        ...


@dataclass(frozen=True)
class ServiceCall:
    """One call through the Gateway. Holds no request or response body (GDPR, untrusted text)."""

    service: str
    operation: str
    run_id: str
    status: CallStatus
    cost: Decimal
    unit: str
    units: int
    latency: timedelta
    error_kind: str | None
    at: datetime


class CallLog(Protocol):
    """Repository port of the Call log, `ServiceCallRepo` in `storage`.

    It is also the monthly spend the Budget reads: `total` must sum the cost of every Service call
    already recorded in that calendar month (UTC), so a restart loses nothing (ADR-0005).
    """

    def record(self, call: ServiceCall) -> None: ...

    def total(self, month_start: date) -> Decimal: ...


@dataclass(frozen=True)
class ServicePolicy:
    """Allow-list entry and traffic limits of one service, from configuration."""

    operations: frozenset[str]
    max_calls: int
    per: timedelta
    max_concurrent: int

    def __post_init__(self) -> None:
        if self.max_calls < 1 or self.max_concurrent < 1 or self.per <= timedelta(0):
            raise ValueError("limits must be positive")


@dataclass(frozen=True)
class GatewayConfig:
    """Everything the Gateway reads from configuration. A service not in `services` is denied."""

    services: dict[str, ServicePolicy]
    run_cap: Decimal
    monthly_cap: Decimal = Decimal(30)
