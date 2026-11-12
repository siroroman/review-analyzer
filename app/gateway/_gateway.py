from collections.abc import Mapping

from app.domain import Clock
from app.gateway._types import (
    CallLog,
    GatewayConfig,
    GatewayResponse,
    ServiceClient,
)


class Gateway:
    """The only way to call a paid service (ADR-0006). Thread-safe; see `call`."""

    def __init__(
        self,
        config: GatewayConfig,
        clients: Mapping[str, ServiceClient],
        clock: Clock,
        call_log: CallLog,
    ) -> None:
        raise NotImplementedError

    def call(self, service: str, operation: str, request: object, *, run_id: str) -> GatewayResponse:
        """Allow-list, limits, `budget.reserve`, the call, `budget.record`, one Service call logged."""
        raise NotImplementedError
