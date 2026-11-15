from datetime import date
from decimal import Decimal

from app.domain import DatePrecision, Insight, InsightType, Review, RunStatus, Source
from tests.api.helpers import HEADERS, Api, cafe

RUN = {"place_ids": ["g1"], "name": "Kavárna", "industry": "cafe"}


def _review(external_id: str, rating: int, *, flagged: bool = False) -> Review:
    return Review(
        source=Source.GOOGLE_MAPS,
        place_external_id="g1",
        external_id=external_id,
        rating=rating,
        text=f"text {external_id}",
        published_on=date(2026, 10, 3),
        date_precision=DatePrecision.DAY,
        language="cs",
        text_hash=f"hash-{external_id}",
        flagged=flagged,
    )


def _start(api: Api) -> str:
    return str(api.client.post("/runs", json=RUN, headers=HEADERS).json()["run_id"])


def _finish(api: Api, run_id: str, last: RunStatus = RunStatus.DONE) -> None:
    for status in (RunStatus.DOWNLOADING, RunStatus.CLASSIFYING, RunStatus.ANALYZING, last):
        api.storage.runs.advance(run_id, status)


def test_a_run_that_is_not_finished_has_no_result_yet() -> None:
    api = Api(known=[cafe()])
    run_id = _start(api)
    assert api.client.get(f"/runs/{run_id}/result", headers=HEADERS).status_code == 409


def test_a_failed_run_has_no_result() -> None:
    api = Api(known=[cafe()])
    run_id = _start(api)
    _finish(api, run_id, RunStatus.FAILED)
    assert api.client.get(f"/runs/{run_id}/result", headers=HEADERS).status_code == 409


def test_the_result_holds_numbers_insights_and_counts() -> None:
    api = Api(known=[cafe()])
    run_id = _start(api)
    api.storage.reviews.add([_review("r1", 5), _review("r2", 3), _review("r3", 1, flagged=True)])
    api.storage.insights.save(
        run_id,
        [
            Insight(
                type=InsightType.SUMMARY,
                period_start=date(2026, 10, 1),
                period_end=date(2026, 10, 31),
                text="Guests like it.",
                review_ids=("r1",),
            )
        ],
    )
    _finish(api, run_id)
    body = api.client.get(f"/runs/{run_id}/result", headers=HEADERS).json()
    assert body["status"] == "done"
    assert (body["reviews"], body["flagged"]) == (3, 1)
    assert body["metrics"]["overall"] == {"average_rating": 4.0, "count": 2}
    assert [insight["text"] for insight in body["insights"]] == ["Guests like it."]
    assert Decimal(body["cost"]) == 0
    assert body["company"]["name"] == "Kavárna"


def test_a_partial_run_has_a_result_too() -> None:
    api = Api(known=[cafe()])
    run_id = _start(api)
    _finish(api, run_id, RunStatus.PARTIAL)
    body = api.client.get(f"/runs/{run_id}/result", headers=HEADERS).json()
    assert (body["status"], body["reviews"], body["metrics"]["overall"]) == ("partial", 0, None)


def test_the_result_needs_a_token() -> None:
    api = Api(known=[cafe()])
    run_id = _start(api)
    assert api.client.get(f"/runs/{run_id}/result").status_code == 401
