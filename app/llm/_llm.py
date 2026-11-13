from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ValidationError

from app.domain import Clock
from app.gateway import ClientError, GatewayResponse, Tokens
from app.llm._types import (
    CompletionGateway,
    CompletionRequest,
    InvalidOutput,
    LlmConfig,
    ModelRef,
    Sleeper,
    TraceEvent,
    TraceOutcome,
    Tracer,
    UnknownTask,
)

_OPERATION = "complete"
# Appended to the caller's prompt on the repair retry. It never repeats the invalid answer or the
# validation error: both can carry text of an untrusted Review.
_REPAIR = (
    "\n\nYour previous answer was not valid JSON for the requested schema. Answer again with only the JSON."
)


@dataclass(frozen=True)
class _Ask[T: BaseModel]:
    """One `complete` call: what the caller asked for."""

    task: str
    prompt: str
    schema: type[T]
    run_id: str
    system: str | None
    cache_system: bool


class Llm:
    """The one entry point to a model: routing, retry, fallback, validation, tracing (ADR-0003, ADR-0006).

    Every provider call goes through `gateway.call`; this module never touches the Budget.
    `BudgetExceeded` and `GatewayDenied` pass through untouched: they are never retried and never
    sent to the fallback.
    """

    def __init__(
        self,
        config: LlmConfig,
        gateway: CompletionGateway,
        clock: Clock,
        sleeper: Sleeper,
        tracer: Tracer,
    ) -> None:
        self._config = config
        self._gateway = gateway
        self._clock = clock
        self._sleeper = sleeper
        self._tracer = tracer

    def complete[T: BaseModel](
        self,
        task: str,
        prompt: str,
        schema: type[T],
        *,
        run_id: str,
        system: str | None = None,
        cache_system: bool = False,
    ) -> T:
        """Run `task` on the model of its route and return the answer as `schema`.

        Raises `UnknownTask`, `InvalidOutput` (no valid JSON from any model), the provider's last
        `ClientError`, `GatewayDenied` or `BudgetExceeded`.
        """
        route = self._config.routes.get(task)
        if route is None:
            raise UnknownTask(task)
        ask = _Ask(task, prompt, schema, run_id, system, cache_system)
        try:
            return self._ask_model(ask, route.primary)
        except (ClientError, InvalidOutput):
            if route.fallback is None:
                raise
        return self._ask_model(ask, route.fallback)

    def _ask_model[T: BaseModel](self, ask: _Ask[T], model: ModelRef) -> T:
        """Call one model with retries on retryable failures and one repair retry on invalid output."""
        prompt = ask.prompt
        retries = 0
        repaired = False
        while True:
            request = CompletionRequest(
                model.model, prompt, ask.system, ask.cache_system, ask.schema.model_json_schema()
            )
            started = self._clock.now()
            try:
                response = self._gateway.call(model.service, _OPERATION, request, run_id=ask.run_id)
            except ClientError as failure:
                self._trace(ask.task, model, started, "error", None)
                if failure.kind not in self._config.retryable_kinds or retries >= self._config.max_retries:
                    raise
                self._sleeper.sleep(self._config.backoff * 2**retries)
                retries += 1
                continue
            text = response.payload if isinstance(response.payload, str) else ""
            try:
                result = ask.schema.model_validate_json(text)
            except ValidationError as invalid:
                self._trace(ask.task, model, started, "invalid", response)
                if repaired:
                    raise InvalidOutput(ask.task, model.model) from invalid
                repaired = True
                prompt = ask.prompt + _REPAIR
                continue
            self._trace(ask.task, model, started, "ok", response)
            return result

    def _trace(
        self,
        task: str,
        model: ModelRef,
        started: datetime,
        outcome: TraceOutcome,
        response: GatewayResponse | None,
    ) -> None:
        usage = response.usage if response is not None else None
        tokens = usage if isinstance(usage, Tokens) else None
        self._tracer.trace(
            TraceEvent(
                task=task,
                service=model.service,
                model=model.model,
                input_tokens=tokens.input if tokens else 0,
                output_tokens=tokens.output if tokens else 0,
                cost=response.cost if response is not None else Decimal(0),
                latency=self._clock.now() - started,
                outcome=outcome,
            )
        )
