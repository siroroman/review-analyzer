import base64
import json
import logging
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Protocol

from pydantic import SecretStr

from app.domain import Clock
from app.llm import TraceEvent
from app.transport import HttpError, HttpRequest, HttpResponse, HttpTransport, read_secret

_log = logging.getLogger(__name__)


class IdSource(Protocol):
    """Port: new unique IDs for Langfuse events. Randomness comes from here, never from the adapter."""

    def new_id(self) -> str: ...


@dataclass(frozen=True)
class LangfuseConfig:
    """Where Langfuse is and the keys to it, read from configuration only. Keys never show in `repr`."""

    host: str
    public_key: SecretStr = field(repr=False)
    secret_key: SecretStr = field(repr=False)
    timeout: float = 10

    @classmethod
    def from_environ(cls, environ: Mapping[str, str]) -> "LangfuseConfig":
        host = environ.get("LANGFUSE_HOST", "https://cloud.langfuse.com").strip().rstrip("/")
        return cls(
            host,
            read_secret(environ, "LANGFUSE_PUBLIC_KEY"),
            read_secret(environ, "LANGFUSE_SECRET_KEY"),
        )


def _iso(moment: datetime) -> str:
    return moment.astimezone(UTC).isoformat().replace("+00:00", "Z")


class LangfuseTracer:
    """Tracer: one Langfuse generation per provider call, with its tokens and price.

    Tracing is not worth a failed Run: any failure of Langfuse is logged (status only, never a key or a
    body) and swallowed.
    """

    def __init__(self, config: LangfuseConfig, transport: HttpTransport, clock: Clock, ids: IdSource) -> None:
        self._config = config
        self._transport = transport
        self._clock = clock
        self._ids = ids
        pair = f"{config.public_key.get_secret_value()}:{config.secret_key.get_secret_value()}"
        self._auth = SecretStr("Basic " + base64.b64encode(pair.encode()).decode())

    def trace(self, event: TraceEvent) -> None:
        end = self._clock.now()
        body: dict[str, object] = {
            "id": self._ids.new_id(),
            "name": event.task,
            "model": event.model,
            "startTime": _iso(end - event.latency),
            "endTime": _iso(end),
            "usageDetails": {
                "input": event.input_tokens,
                "output": event.output_tokens,
                "total": event.input_tokens + event.output_tokens,
            },
            "costDetails": {"total": float(event.cost)},
            "metadata": {"service": event.service, "outcome": event.outcome},
        }
        if event.outcome != "ok":
            body["level"] = "ERROR"
            body["statusMessage"] = event.outcome
        item = {"id": self._ids.new_id(), "type": "generation-create", "timestamp": _iso(end), "body": body}
        request = HttpRequest(
            "POST",
            f"{self._config.host}/api/public/ingestion",
            {"Authorization": self._auth.get_secret_value(), "Content-Type": "application/json"},
            json.dumps({"batch": [item]}).encode(),
            self._config.timeout,
        )
        try:
            response = self._transport.send(request)
        except HttpError:
            _log.warning("langfuse: trace not sent (no answer)")
            return
        problem = _problem(response)
        if problem:
            _log.warning("langfuse: trace not stored (%s)", problem)


def _problem(response: HttpResponse) -> str | None:
    """Why Langfuse did not store the event, as a short word; `None` when it did."""
    if response.status not in (200, 201, 207):
        return f"status {response.status}"
    try:
        parsed = json.loads(response.body)
    except ValueError:
        return "unreadable answer"
    if not isinstance(parsed, dict) or parsed.get("errors"):
        return "rejected event"
    return None
