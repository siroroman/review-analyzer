from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Protocol

from pydantic import SecretStr


@dataclass(frozen=True)
class HttpRequest:
    """One HTTPS call. `headers` may carry a key: never log or print a request."""

    method: str
    url: str
    headers: Mapping[str, str] = field(repr=False)
    body: bytes = field(repr=False)
    timeout: float


@dataclass(frozen=True)
class HttpResponse:
    """The status and raw body of an answer, whatever the status."""

    status: int
    body: bytes = field(repr=False)


class HttpError(Exception):
    """The call got no answer. The message never holds the URL, a header or a body."""


class HttpTimeout(HttpError):
    """No answer within the request's timeout."""


class HttpTransport(Protocol):
    """Port: sends one HTTP request. Adapters of paid services and of Langfuse sit on top of it."""

    def send(self, request: HttpRequest) -> HttpResponse:
        """Return the answer for any status. Raise `HttpTimeout` or `HttpError` when there is none."""
        ...


class MissingSecret(Exception):
    """A required key is not configured. Names the setting, never a value."""

    def __init__(self, name: str) -> None:
        super().__init__(f"missing configuration: {name}")
        self.name = name


def read_secret(environ: Mapping[str, str], name: str) -> SecretStr:
    """A key from configuration. The only way adapters get a key: never a literal, never `os.environ`."""
    value = environ.get(name, "").strip()
    if not value:
        raise MissingSecret(name)
    return SecretStr(value)
