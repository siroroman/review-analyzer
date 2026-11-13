"""Gateway: the only way to call a paid service. Allow-list, traffic limits, Budget, Call log (ADR-0006)."""

from app.budget import BudgetExceeded, Tokens, Units
from app.gateway._anthropic import AnthropicClient
from app.gateway._fakes import FakeCallLog, FakeServiceClient
from app.gateway._gateway import Gateway
from app.gateway._google_places import (
    GOOGLE_PLACES,
    AutocompleteRequest,
    DetailsRequest,
    GooglePage,
    GooglePlacesClient,
    Suggestion,
    TextSearchRequest,
)
from app.gateway._openrouter import OpenRouterClient
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
    "GOOGLE_PLACES",
    "AnthropicClient",
    "AutocompleteRequest",
    "BudgetExceeded",
    "CallLog",
    "CallStatus",
    "ClientError",
    "ClientResponse",
    "ClientTimeout",
    "DeniedReason",
    "DetailsRequest",
    "FakeCallLog",
    "FakeServiceClient",
    "Gateway",
    "GatewayConfig",
    "GatewayDenied",
    "GatewayResponse",
    "GooglePage",
    "GooglePlacesClient",
    "OpenRouterClient",
    "ServiceCall",
    "ServiceClient",
    "ServicePolicy",
    "Suggestion",
    "TextSearchRequest",
    "Tokens",
    "Units",
    "Usage",
]
