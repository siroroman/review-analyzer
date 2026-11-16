from datetime import UTC, datetime, timedelta
from decimal import Decimal

from tests.api.helpers import ADMIN, HEADERS, Api
from tests.storage.helpers import call

AUTH = {"Authorization": f"Bearer {ADMIN}"}
NOW = datetime(2026, 11, 13, 9, 0, tzinfo=UTC)


def seeded() -> Api:
    api = Api()  # the fake Clock stands at 2026-11-13 09:00 UTC
    calls = api.storage.calls
    calls.record(call("apify", "run_actor", "run-1", cost="2", at=NOW - timedelta(days=20)))  # October
    calls.record(call("apify", "run_actor", "run-1", cost="1", at=NOW - timedelta(days=1)))
    calls.record(call("openrouter", "classify", "run-1", cost="0.25", at=NOW))
    calls.record(call("openrouter", "classify", "run-2", status="failed", cost="0.25", at=NOW))
    return api


def test_spend_without_a_token_or_with_a_demo_token_is_401() -> None:
    api = seeded()
    assert api.client.get("/admin/spend").status_code == 401
    assert api.client.get("/admin/spend", headers=HEADERS).status_code == 401
    assert api.client.get("/admin/calls", headers=HEADERS).status_code == 401
    assert api.client.get("/admin/calls", headers={"Authorization": "Bearer nope"}).status_code == 401


def test_spend_adds_up_per_service_day_and_run() -> None:
    body = seeded().client.get("/admin/spend", headers=AUTH).json()
    assert {k: Decimal(v) for k, v in body["by_service"].items()} == {
        "apify": Decimal(3),
        "openrouter": Decimal("0.5"),
    }
    assert {k: Decimal(v) for k, v in body["by_day"].items()}["2026-11-13"] == Decimal("0.5")
    assert {k: Decimal(v) for k, v in body["by_run"].items()} == {
        "run-1": Decimal("3.25"),
        "run-2": Decimal("0.25"),
    }


def test_spend_shows_the_month_and_the_share_of_the_cap_used() -> None:
    body = seeded().client.get("/admin/spend", headers=AUTH).json()
    assert Decimal(body["month_total"]) == Decimal("1.5")  # October is not in November
    assert Decimal(body["monthly_cap"]) == Decimal(30)
    assert Decimal(body["share_of_cap"]) == Decimal("0.05")


def test_spend_can_be_limited_to_a_date_range() -> None:
    since = (NOW - timedelta(days=2)).isoformat()
    body = seeded().client.get("/admin/spend", params={"since": since}, headers=AUTH).json()
    assert {k: Decimal(v) for k, v in body["by_service"].items()}["apify"] == Decimal(1)


def test_the_monthly_cap_comes_from_configuration() -> None:
    body = Api(monthly_cap=Decimal(10)).client.get("/admin/spend", headers=AUTH).json()
    assert Decimal(body["monthly_cap"]) == Decimal(10)
    assert Decimal(body["share_of_cap"]) == Decimal(0)


def test_calls_are_listed_oldest_first_without_bodies() -> None:
    body = seeded().client.get("/admin/calls", headers=AUTH).json()
    assert body["total"] == 4
    assert [item["cost"] for item in body["items"]] == ["2", "1", "0.25", "0.25"]
    assert set(body["items"][0]) == {
        "service",
        "operation",
        "run_id",
        "status",
        "cost",
        "unit",
        "units",
        "latency_ms",
        "error_kind",
        "at",
    }


def test_calls_filter_by_service_operation_run_and_status() -> None:
    client = seeded().client

    def count(**params: str) -> int:
        return int(client.get("/admin/calls", params=params, headers=AUTH).json()["total"])

    assert count(service="apify") == 2
    assert count(operation="classify") == 2
    assert count(run_id="run-2") == 1
    assert count(status="failed") == 1
    assert count(service="apify", status="failed") == 0


def test_calls_filter_by_a_half_open_date_range() -> None:
    client = seeded().client
    params = {"since": (NOW - timedelta(days=1)).isoformat(), "until": NOW.isoformat()}
    assert client.get("/admin/calls", params=params, headers=AUTH).json()["total"] == 1


def test_calls_are_paginated() -> None:
    client = seeded().client
    page = client.get("/admin/calls", params={"limit": 2, "offset": 1}, headers=AUTH).json()
    assert page["total"] == 4
    assert [item["cost"] for item in page["items"]] == ["1", "0.25"]
    assert client.get("/admin/calls", params={"limit": 0}, headers=AUTH).status_code == 422
    assert client.get("/admin/calls", params={"status": "weird"}, headers=AUTH).status_code == 422


def test_the_admin_endpoints_are_documented_in_openapi() -> None:
    schema = Api().client.get("/openapi.json").json()
    assert {"/admin/spend", "/admin/calls"} <= set(schema["paths"])
    assert "summary" in schema["paths"]["/admin/calls"]["get"]


def test_a_date_without_a_utc_offset_is_422_not_a_crash() -> None:
    client = seeded().client
    for path in ("/admin/calls", "/admin/spend"):
        for name in ("since", "until"):
            assert client.get(path, params={name: "2026-11-11T09:00:00"}, headers=AUTH).status_code == 422
