from collections.abc import Sequence
from datetime import timedelta

from fastapi.testclient import TestClient
from pydantic import SecretStr

from app.api import ApiConfig, FakeQueue, create_app
from app.domain import Clock, Place, Source
from app.gateway import Suggestion
from app.pipeline import RunReport
from app.storage import Storage, UnknownRun, in_memory_storage
from tests.places.helpers import Setup, google

DEMO = "demo-token-1"
OTHER_DEMO = "demo-token-2"
ADMIN = "admin-token-1"
HEADERS = {"Authorization": f"Bearer {DEMO}"}


def config(**changes: object) -> ApiConfig:
    base = ApiConfig(
        demo_tokens=(SecretStr(DEMO), SecretStr(OTHER_DEMO)),
        admin_token=SecretStr(ADMIN),
        requests_per_minute=1000,
        runs_per_day=100,
    )
    return base.model_copy(update=changes)


class FakeReporter:
    """A `Reporter` with the reports a test put in."""

    def __init__(self) -> None:
        self.reports: dict[str, RunReport] = {}

    def report(self, run_id: str) -> RunReport:
        if run_id not in self.reports:
            raise UnknownRun(run_id)
        return self.reports[run_id]


class Api:
    """The app over in-memory storage, `places` over a fake Google, a fake queue and a fake clock."""

    def __init__(self, *, known: Sequence[Place] = (), run_cap: str = "5", **changes: object) -> None:
        self.setup = Setup(run_cap=run_cap)
        self.clock: Clock = self.setup.clock
        self.storage: Storage = in_memory_storage(self.clock)
        self.queue = FakeQueue()
        self.reporter = FakeReporter()
        for place in known:
            self.setup.google.known[place.external_id] = place
        self.app = create_app(
            storage=self.storage,
            places=self.setup.places,
            queue=self.queue,
            pipeline=self.reporter,
            clock=self.clock,
            config=config(**changes),
        )
        self.client = TestClient(self.app)

    def advance(self, by: timedelta) -> None:
        self.setup.clock.advance(by)


def cafe(external_id: str = "g1") -> Place:
    return google(external_id, "Kavárna", "Praha")


def suggestion(place_id: str, text: str) -> Suggestion:
    return Suggestion(place_id, text)


__all__ = ["ADMIN", "DEMO", "HEADERS", "OTHER_DEMO", "Api", "Source", "cafe", "config", "suggestion"]
