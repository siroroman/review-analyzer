from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from pydantic import BaseModel

from app.domain import FakeClock
from app.gateway import (
    ClientResponse,
    FakeCallLog,
    FakeServiceClient,
    Gateway,
    GatewayConfig,
    ServicePolicy,
    Tokens,
)
from app.llm import CompletionRequest, FakeSleeper, FakeTracer, Llm, LlmConfig, ModelRef, Route

D = Decimal
START = datetime(2026, 11, 12, 8, 0, tzinfo=UTC)

JEV = ModelRef("openrouter", "jev-1.14")
CHAT = ModelRef("openrouter_chat", "deepseek-v4.1-flash")
SECOND = ModelRef("openrouter_chat", "deepseek-alt")

# Placeholder prices of app/budget/_estimate.py: DeepSeek 0.30 / 1.20 USD per million tokens.
CHAT_USAGE = Tokens("openrouter_chat", "deepseek-v4.1-flash", 500_000, 250_000)  # 0.15 + 0.30 = 0.45 USD
JEV_USAGE = Tokens("openrouter", "jev-1.14", 10_000, 0)  # 0.001 USD

VALID = '{"label": "service", "score": 3}'


class Answer(BaseModel):
    label: str
    score: int


Step = str | Exception


def requests(client: FakeServiceClient) -> list[CompletionRequest]:
    """The requests a fake provider received, typed."""
    return [request for _, request in client.calls if isinstance(request, CompletionRequest)]


def scripted(
    usage: Tokens, *steps: Step, clock: FakeClock | None = None, took: timedelta = timedelta(0)
) -> FakeServiceClient:
    """A fake provider that plays `steps` in order: a string is the answer, an exception is raised."""
    remaining = list(steps)

    def respond(_operation: str, _request: object) -> ClientResponse:
        if clock is not None:
            clock.advance(took)
        step = remaining.pop(0)
        if isinstance(step, Exception):
            raise step
        return ClientResponse(step, usage)

    return FakeServiceClient(usage, respond)


def policy() -> ServicePolicy:
    return ServicePolicy(frozenset({"complete"}), 100, timedelta(seconds=60), 4)


class Setup:
    """An Llm over the real Gateway with fake providers, a fake clock, sleeper, tracer and Call log."""

    def __init__(
        self,
        jev: Callable[[FakeClock], FakeServiceClient] | None = None,
        chat: Callable[[FakeClock], FakeServiceClient] | None = None,
        routes: dict[str, Route] | None = None,
        run_cap: str = "5",
        monthly_cap: str = "30",
        max_retries: int = 2,
        took: timedelta = timedelta(0),
    ) -> None:
        self.clock = FakeClock(START)
        self.sleeper = FakeSleeper(self.clock)
        self.tracer = FakeTracer()
        self.log = FakeCallLog()
        self.openrouter = jev(self.clock) if jev else scripted(JEV_USAGE, VALID, clock=self.clock, took=took)
        self.chat = chat(self.clock) if chat else scripted(CHAT_USAGE, VALID, clock=self.clock, took=took)
        gateway = Gateway(
            GatewayConfig({"openrouter": policy(), "openrouter_chat": policy()}, D(run_cap), D(monthly_cap)),
            {"openrouter": self.openrouter, "openrouter_chat": self.chat},
            self.clock,
            self.log,
        )
        config = LlmConfig(
            routes=routes
            if routes is not None
            else {"classify": Route(JEV, CHAT), "insights": Route(SECOND)},
            max_retries=max_retries,
            backoff=timedelta(seconds=1),
        )
        self.llm = Llm(config, gateway, self.clock, self.sleeper, self.tracer)
