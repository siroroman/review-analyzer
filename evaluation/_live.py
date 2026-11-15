"""The real Llm for a manual run: keys from the environment, paid calls through the Gateway (ADR-0006).

Not tested: it only wires real adapters, and a test would call a paid service. A real Clock and Sleeper do not
exist in `app/` yet; the two below are the smallest ones, for this command only.
"""

import os
import threading
import time
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from app.classification import TASK
from app.domain import Clock
from app.gateway import AnthropicClient, Gateway, GatewayConfig, OpenRouterClient, ServicePolicy
from app.llm import FakeTracer, Llm, LlmConfig, ModelRef, Route
from app.storage import in_memory_storage
from app.transport import UrllibTransport, read_secret

JEV = ModelRef("openrouter", "jev-1.14")
HAIKU = ModelRef("anthropic", "claude-haiku")
RUN_CAP = Decimal(1)  # one evaluation of 200 Reviews costs cents; a loop must still stop at 1 USD


class _SystemClock:
    def now(self) -> datetime:
        return datetime.fromtimestamp(time.time(), UTC)


class _Sleeper:
    def sleep(self, delay: timedelta) -> None:
        threading.Event().wait(delay.total_seconds())


def live_llm() -> tuple[Llm, Clock, str]:
    """Raises `MissingSecret` (names the variable, never a value) when a key is not set."""
    clock = _SystemClock()
    transport = UrllibTransport()
    openrouter = OpenRouterClient(
        read_secret(os.environ, "OPENROUTER_API_KEY"), transport, {"jev-1.14": "typesafe/jev-1.14"}
    )
    anthropic = AnthropicClient(
        read_secret(os.environ, "ANTHROPIC_API_KEY"), transport, {"claude-haiku": "claude-haiku-5-5"}
    )
    policy = ServicePolicy(frozenset({"complete"}), 100, timedelta(seconds=60), 2)
    gateway = Gateway(
        GatewayConfig({"openrouter": policy, "anthropic": policy}, RUN_CAP),
        {"openrouter": openrouter, "anthropic": anthropic},
        clock,
        in_memory_storage(clock).calls,
    )
    config = LlmConfig(routes={TASK: Route(JEV, HAIKU)})
    # Langfuse traces are for real Runs; an evaluation would only fill them with test Reviews.
    return (
        Llm(config, gateway, clock, _Sleeper(), FakeTracer()),
        clock,
        f"{JEV.model}, fallback {HAIKU.model}",
    )
