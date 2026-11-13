from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from pydantic import SecretStr

from app.domain import FakeClock
from app.gateway import (
    SCRAPE_GOOGLE_REVIEWS,
    ApifyClient,
    ClientError,
    FakeCallLog,
    Gateway,
    GatewayConfig,
    ReviewScrape,
    ServicePolicy,
)
from app.transport import FakeTransport, HttpResponse, HttpTimeout


def run(step: HttpResponse | HttpTimeout) -> tuple[FakeCallLog, Exception | None]:
    log = FakeCallLog()
    policy = ServicePolicy(frozenset({SCRAPE_GOOGLE_REVIEWS}), 10, timedelta(seconds=60), 2)
    clock = FakeClock(datetime(2026, 11, 13, 18, 0, tzinfo=UTC))
    config = GatewayConfig({"apify": policy}, Decimal(5))
    client = ApifyClient(SecretStr("x"), FakeTransport(step))
    gateway = Gateway(config, {"apify": client}, clock, log)
    try:
        gateway.call("apify", SCRAPE_GOOGLE_REVIEWS, ReviewScrape("p", None, 500), run_id="r")
    except ClientError as failure:
        return log, failure
    return log, None


@pytest.mark.parametrize("step", [HttpTimeout(), HttpResponse(408, b"{}")])
def test_a_timed_out_run_is_booked_at_the_estimate_because_apify_still_bills_it(
    step: HttpResponse | HttpTimeout,
) -> None:
    log, failure = run(step)
    assert failure is not None and failure.kind == "timeout"
    assert [(c.status, c.cost, c.units) for c in log.calls] == [("failed", Decimal("0.30"), 500)]


def test_a_refused_run_is_booked_at_zero() -> None:
    log, _ = run(HttpResponse(401, b"{}"))
    assert [(c.status, c.cost) for c in log.calls] == [("failed", Decimal(0))]
