"""Gateway: the only way to call a paid service. Allow-list, traffic limits, Budget, Call log (ADR-0006)."""

from app.budget import BudgetExceeded, Tokens, Units
from app.gateway._fakes import FakeCallLog, FakeServiceClient
from app.gateway._gateway import Gateway
from app.gateway._types import (
    CallLog,
    CallStatus,
    ClientError,
    ClientResponse,
    ClientTimeout,
    DeniedReason,
    GatewayConfig,
    GatewayDenied,
    GatewayResponse,
    ServiceCall,
    ServiceClient,
    ServicePolicy,
    Usage,
)

__all__ = [
    "BudgetExceeded",
    "CallLog",
    "CallStatus",
    "ClientError",
    "ClientResponse",
    "ClientTimeout",
    "DeniedReason",
    "FakeCallLog",
    "FakeServiceClient",
    "Gateway",
    "GatewayConfig",
    "GatewayDenied",
    "GatewayResponse",
    "ServiceCall",
    "ServiceClient",
    "ServicePolicy",
    "Tokens",
    "Units",
    "Usage",
]
