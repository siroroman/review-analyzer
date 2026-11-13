from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import timedelta
from decimal import Decimal
from typing import Literal, Protocol

from app.gateway import GatewayResponse

TraceOutcome = Literal["ok", "invalid", "error"]


class LlmError(Exception):
    """Base of what `llm` raises itself. Errors of the gateway and the provider pass through unchanged."""


class UnknownTask(LlmError):
    """The task has no route in the routing table. Nothing was called."""

    def __init__(self, task: str) -> None:
        super().__init__(f"no route for task {task!r}")
        self.task = task


class InvalidOutput(LlmError):
    """The model answered, but not with valid JSON for the schema, even after the repair retry."""

    def __init__(self, task: str, model: str) -> None:
        super().__init__(f"{task}: {model} gave no valid output")
        self.task = task
        self.model = model


@dataclass(frozen=True)
class ModelRef:
    """One model of one paid service, as the gateway knows the service."""

    service: str
    model: str


@dataclass(frozen=True)
class Route:
    """Where a task goes: the model it uses and the model it falls back to."""

    primary: ModelRef
    fallback: ModelRef | None = None


@dataclass(frozen=True)
class LlmConfig:
    """Everything `llm` reads from configuration.

    `max_retries` is the number of repeats per model after a retryable failure; the delay before
    repeat n is `backoff * 2 ** (n - 1)`. `retryable_kinds` are the `ClientError.kind` words worth
    repeating on the same model; any other failure goes straight to the fallback.
    """

    routes: Mapping[str, Route]
    max_retries: int = 2
    backoff: timedelta = timedelta(seconds=1)
    retryable_kinds: frozenset[str] = field(default_factory=lambda: frozenset({"timeout", "server_error"}))

    def __post_init__(self) -> None:
        if self.max_retries < 0 or self.backoff < timedelta(0):
            raise ValueError("max_retries and backoff must not be negative")


@dataclass(frozen=True)
class CompletionRequest:
    """The request `llm` sends through the gateway as operation `complete`."""

    model: str
    prompt: str
    system: str | None
    cache_system: bool
    json_schema: dict[str, object]


@dataclass(frozen=True)
class TraceEvent:
    """What the Tracer gets for one provider call. `cost` is 0 for a failed call (the Call log has it)."""

    task: str
    service: str
    model: str
    input_tokens: int
    output_tokens: int
    cost: Decimal
    latency: timedelta
    outcome: TraceOutcome


class Tracer(Protocol):
    """Port: records one model call (adapter: Langfuse)."""

    def trace(self, event: TraceEvent) -> None: ...


class Sleeper(Protocol):
    """Port: waits between retries. Tests never sleep (ADR-0004)."""

    def sleep(self, delay: timedelta) -> None: ...


class CompletionGateway(Protocol):
    """The part of `gateway.Gateway` that `llm` uses."""

    def call(self, service: str, operation: str, request: object, *, run_id: str) -> GatewayResponse: ...
