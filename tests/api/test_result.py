from datetime import date
from decimal import Decimal

from app.domain import (
    Change,
    ChangeKind,
    Company,
    Insight,
    InsightType,
    Metrics,
    PlaceDetails,
    PlaceResult,
    RatingSummary,
    RunStatus,
    Source,
    StarCount,
    Topic,
)
from app.pipeline import NOTE_INDUSTRY_FALLBACK, RunReport, RunResult
from tests.api.helpers import HEADERS, Api, cafe
from tests.storage.helpers import call

RUN = {"place_ids": ["g1"]}


def _start(api: Api) -> str:
    return str(api.client.post("/runs", json=RUN, headers=HEADERS).json()["run_id"])


def _finish(api: Api, run_id: str, last: RunStatus = RunStatus.DONE) -> None:
    for status in (RunStatus.DOWNLOADING, RunStatus.CLASSIFYING, RunStatus.ANALYZING, last):
        api.storage.runs.advance(run_id, status)


def _report(
    run_id: str,
    status: RunStatus,
    notes: tuple[str, ...] = (),
    places: tuple[PlaceResult, ...] = (),
) -> RunReport:
    insight = Insight(
        type=InsightType.SUMMARY,
        period_start=date(2026, 10, 1),
        period_end=date(2026, 10, 31),
        text="Guests like it.",
        review_ids=("r1",),
    )
    result = RunResult(
        run_id=run_id,
        status=status,
        reviews=3,
        flagged=1,
        unclassified=2,
        insights=1,
        trend_points=0,
        cost=Decimal("0.25"),
        notes=notes,
    )
    drop = Change(
        kind=ChangeKind.DROP,
        source=Source.GOOGLE_MAPS,
        period_start=date(2026, 10, 1),
        delta=-0.8,
        main_topic_key="staff",
    )
    metrics = Metrics(
        trend=(),
        topic_shares=(),
        changes=(drop,),
        overall=RatingSummary(average_rating=4.0, count=2),
        rating_counts=(StarCount(stars=5, count=1), StarCount(stars=3, count=1)),
    )
    company = Company(name="Kavárna", places=(cafe(),))
    topics = (Topic(key="staff", name="Obsluha", description="Friendliness of the staff"),)
    return RunReport(
        result=result, company=company, metrics=metrics, insights=(insight,), topics=topics, places=places
    )


def test_a_run_that_is_not_finished_has_no_result_yet() -> None:
    api = Api(known=[cafe()])
    run_id = _start(api)
    assert api.client.get(f"/runs/{run_id}/result", headers=HEADERS).status_code == 409


def test_a_failed_run_has_no_result() -> None:
    api = Api(known=[cafe()])
    run_id = _start(api)
    _finish(api, run_id, RunStatus.FAILED)
    assert api.client.get(f"/runs/{run_id}/result", headers=HEADERS).status_code == 409


def test_the_result_is_what_the_pipeline_reports() -> None:
    api = Api(known=[cafe()])
    run_id = _start(api)
    _finish(api, run_id)
    api.reporter.reports[run_id] = _report(run_id, RunStatus.DONE)
    body = api.client.get(f"/runs/{run_id}/result", headers=HEADERS).json()
    assert body["status"] == "done"
    assert (body["reviews"], body["flagged"], body["unclassified"]) == (3, 1, 2)
    assert body["metrics"]["overall"] == {"average_rating": 4.0, "count": 2}
    assert body["metrics"]["changes"] == [
        {
            "kind": "drop",
            "source": "google_maps",
            "period_start": "2026-10-01",
            "delta": -0.8,
            "main_topic_key": "staff",
        }
    ]
    assert body["metrics"]["rating_counts"] == [{"stars": 5, "count": 1}, {"stars": 3, "count": 1}]
    assert body["topics"] == [{"key": "staff", "name": "Obsluha"}]
    assert [insight["text"] for insight in body["insights"]] == ["Guests like it."]
    assert Decimal(body["cost"]) == Decimal("0.25")
    assert body["company"]["name"] == "Kavárna"


def test_the_result_says_when_the_industry_could_not_be_inferred() -> None:
    api = Api(known=[cafe()])
    run_id = _start(api)
    _finish(api, run_id)
    api.reporter.reports[run_id] = _report(run_id, RunStatus.DONE, (NOTE_INDUSTRY_FALLBACK,))
    body = api.client.get(f"/runs/{run_id}/result", headers=HEADERS).json()
    assert body["notes"] == ["industry_fallback"]


def test_a_result_without_notes_has_an_empty_list() -> None:
    api = Api(known=[cafe()])
    run_id = _start(api)
    _finish(api, run_id)
    api.reporter.reports[run_id] = _report(run_id, RunStatus.DONE)
    assert api.client.get(f"/runs/{run_id}/result", headers=HEADERS).json()["notes"] == []


def test_a_partial_run_has_a_result_too() -> None:
    api = Api(known=[cafe()])
    run_id = _start(api)
    _finish(api, run_id, RunStatus.PARTIAL)
    api.reporter.reports[run_id] = _report(run_id, RunStatus.PARTIAL)
    assert api.client.get(f"/runs/{run_id}/result", headers=HEADERS).json()["status"] == "partial"


def test_a_run_the_pipeline_does_not_know_is_404() -> None:
    api = Api(known=[cafe()])
    run_id = _start(api)
    _finish(api, run_id)
    assert api.client.get(f"/runs/{run_id}/result", headers=HEADERS).status_code == 404


def test_the_result_needs_a_token() -> None:
    api = Api(known=[cafe()])
    run_id = _start(api)
    assert api.client.get(f"/runs/{run_id}/result").status_code == 401


def test_the_result_splits_the_cost_by_service_and_the_parts_sum_to_the_cost() -> None:
    api = Api(known=[cafe()])
    run_id = _start(api)
    _finish(api, run_id)
    api.reporter.reports[run_id] = _report(run_id, RunStatus.DONE)
    for service, cost in (
        ("apify", "0.1"),
        ("openrouter", "0.05"),
        ("openrouter_chat", "0.07"),
        ("other", "0.03"),
    ):
        api.storage.calls.record(call(service=service, run_id=run_id, cost=cost))
    api.storage.calls.record(call(service="apify", run_id="another", cost="9"))
    body = api.client.get(f"/runs/{run_id}/result", headers=HEADERS).json()
    split = {name: Decimal(value) for name, value in body["cost_by_service"].items()}
    assert split == {
        "apify": Decimal("0.1"),
        "models": Decimal("0.12"),
        "google_places": Decimal(0),
        "other": Decimal("0.03"),
    }
    assert sum(split.values()) == Decimal("0.25") == Decimal(body["cost"])


def _place_result(details: PlaceDetails | None, analyzed: int, limited: bool = False) -> PlaceResult:
    return PlaceResult(
        source=Source.GOOGLE_MAPS,
        place_external_id="g1",
        details=details,
        analyzed_count=analyzed,
        analyzed_is_limited=limited,
    )


def _places_of(api: Api, place: PlaceResult) -> list[dict[str, object]]:
    run_id = _start(api)
    _finish(api, run_id)
    api.reporter.reports[run_id] = _report(run_id, RunStatus.DONE, places=(place,))
    body = api.client.get(f"/runs/{run_id}/result", headers=HEADERS).json()
    places: list[dict[str, object]] = body["places"]
    return places


def test_the_result_has_the_totals_and_details_of_each_place() -> None:
    details = PlaceDetails(
        rating=4.3,
        review_count=26348,
        reviews_per_rating={5: 20000, 4: 4000, 3: 1000, 2: 500, 1: 848},
        category="Cafe",
        address="Praha 1",
        phone="+420 123 456 789",
        website="https://example.cz",
        maps_url="https://maps.google.com/?cid=1",
        thumbnail_url="https://example.cz/t.jpg",
    )
    (place,) = _places_of(Api(known=[cafe()]), _place_result(details, 1000, limited=True))
    assert place == {
        "source": "google_maps",
        "place_external_id": "g1",
        "category": "Cafe",
        "address": "Praha 1",
        "phone": "+420 123 456 789",
        "website": "https://example.cz",
        "maps_url": "https://maps.google.com/?cid=1",
        "thumbnail_url": "https://example.cz/t.jpg",
        "rating": 4.3,
        "review_count": 26348,
        "reviews_per_rating": {"5": 20000, "4": 4000, "3": 1000, "2": 500, "1": 848},
        "analyzed_count": 1000,
        "analyzed_is_limited": True,
    }


def test_the_limited_flag_is_what_the_pipeline_reports() -> None:
    (limited,) = _places_of(
        Api(known=[cafe()]), _place_result(PlaceDetails(rating=4, review_count=26348), 1000, True)
    )
    (whole,) = _places_of(Api(known=[cafe()]), _place_result(PlaceDetails(rating=4, review_count=800), 800))
    assert (limited["analyzed_is_limited"], whole["analyzed_is_limited"]) == (True, False)


def test_a_place_without_details_has_null_totals_and_still_its_analyzed_count() -> None:
    (place,) = _places_of(Api(known=[cafe()]), _place_result(None, 40))
    google_fields = ("category", "address", "phone", "website", "maps_url", "thumbnail_url")
    assert [place[f] for f in google_fields] == [None] * 6
    assert (place["rating"], place["review_count"], place["reviews_per_rating"]) == (None, None, None)
    assert (place["analyzed_count"], place["analyzed_is_limited"]) == (40, False)
