"""What the model-provider adapters share: the request shape, status mapping and token estimate."""

import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from app.gateway._types import ClientError, ClientTimeout
from app.transport import HttpError, HttpRequest, HttpResponse, HttpTimeout, HttpTransport

OPERATION = "complete"
_CHARS_PER_TOKEN = 3  # Czech text is token-hungry: 3 characters per token overestimates, which is safe.


@runtime_checkable
class ModelRequest(Protocol):
    """The request `llm` sends as operation `complete` (`llm.CompletionRequest`), seen from the gateway."""

    @property
    def model(self) -> str: ...
    @property
    def prompt(self) -> str: ...
    @property
    def system(self) -> str | None: ...
    @property
    def cache_system(self) -> bool: ...
    @property
    def json_schema(self) -> dict[str, object]: ...


def model_request(operation: str, request: object) -> ModelRequest:
    """The typed request, or a `ClientError` before any call is made."""
    if operation != OPERATION:
        raise ClientError("unsupported_operation")
    if not isinstance(request, ModelRequest):
        raise ClientError("bad_request")
    return request


def tokens_in(*texts: str | None) -> int:
    """A deliberately high count of the input tokens of these texts."""
    return sum(len(text) for text in texts if text) // _CHARS_PER_TOKEN + 1


def error_kind(status: int) -> str:
    """A short machine word for an error status. Never part of a body."""
    if status == 429:
        return "rate_limited"
    if status in (401, 403):
        return "auth"
    if status == 402:
        return "payment"
    if status in (400, 413, 422):
        return "bad_request"
    if status >= 500:
        return "server_error"
    return "http_error"


@dataclass(frozen=True)
class Exchange:
    """The answer of a provider, parsed as a JSON object."""

    body: Mapping[str, object]


def send(transport: HttpTransport, request: HttpRequest) -> Exchange:
    """Send, and turn every failure into a `ClientError` that holds no body, URL or key."""
    try:
        response = transport.send(request)
    except HttpTimeout:
        raise ClientTimeout() from None
    except HttpError:
        raise ClientError("connection_error") from None
    return _parse(response)


def _parse(response: HttpResponse) -> Exchange:
    if response.status != 200:
        raise ClientError(error_kind(response.status))
    try:
        parsed = json.loads(response.body)
    except ValueError:
        raise ClientError("bad_response") from None
    if not isinstance(parsed, dict):
        raise ClientError("bad_response")
    return Exchange(parsed)


def count(value: object) -> int:
    """A token count from a provider answer; anything else is a bad response."""
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ClientError("bad_response")
    return value
