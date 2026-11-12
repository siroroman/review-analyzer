from datetime import UTC, datetime, timedelta
from decimal import Decimal

from app.domain import FakeClock
from app.gateway import (
    ClientResponse,
    FakeCallLog,
    FakeServiceClient,
    Gateway,
    GatewayConfig,
    ServicePolicy,
    Tokens,
    Units,
)

D = Decimal
START = datetime(2026, 11, 12, 8, 0, tzinfo=UTC)

# Placeholder prices of app/budget/_estimate.py: haiku 1 / 5 USD per million tokens, Places details 0.017.
HAIKU_700K = Tokens("anthropic", "claude-haiku", 200_000, 100_000)  # 0.2 + 0.5 = 0.7 USD
PLACES_ONE = Units("google_places", "details_request", 1)  # 0.017 USD


def policy(
    operations: tuple[str, ...] = ("complete",),
    max_calls: int = 100,
    per: timedelta = timedelta(seconds=60),
    max_concurrent: int = 4,
) -> ServicePolicy:
    return ServicePolicy(frozenset(operations), max_calls, per, max_concurrent)


def ok_client(usage: Tokens | Units = HAIKU_700K, payload: object = "answer") -> FakeServiceClient:
    return FakeServiceClient(usage, lambda _op, _req: ClientResponse(payload, usage))


class Setup:
    """A Gateway over fake clients, a fake clock and a fake Call log."""

    def __init__(
        self,
        clients: dict[str, FakeServiceClient] | None = None,
        services: dict[str, ServicePolicy] | None = None,
        run_cap: str = "5",
        monthly_cap: str = "30",
        took: timedelta = timedelta(0),
    ) -> None:
        self.clock = FakeClock(START)
        self.log = FakeCallLog()
        self.clients = clients if clients is not None else {"anthropic": self.client(took=took)}
        config = GatewayConfig(
            services=services if services is not None else {"anthropic": policy()},
            run_cap=D(run_cap),
            monthly_cap=D(monthly_cap),
        )
        self.gateway = Gateway(config, self.clients, self.clock, self.log)

    def client(self, usage: Tokens | Units = HAIKU_700K, took: timedelta = timedelta(0)) -> FakeServiceClient:
        """A client that answers after `took` on this setup's fake clock."""

        def respond(_op: str, _req: object) -> ClientResponse:
            self.clock.advance(took)
            return ClientResponse("answer", usage)

        return FakeServiceClient(usage, respond)
