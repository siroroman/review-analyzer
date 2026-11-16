from datetime import timedelta
from decimal import Decimal
from typing import Any

from app.domain import ReviewTopic, RunStatus, Sentiment, Source, Taxonomy, Topic
from app.storage import StoredTaxonomy
from tests.api.helpers import HEADERS, Api, cafe
from tests.storage.helpers import call, review

RUN = {"place_ids": ["g1"], "name": "Kavárna", "industry": "cafe"}
MINUTE = timedelta(minutes=1)


def _start(api: Api) -> str:
    run_id: str = api.client.post("/runs", json=RUN, headers=HEADERS).json()["run_id"]
    return run_id


def _status(api: Api, run_id: str) -> dict[str, Any]:
    body: dict[str, Any] = api.client.get(f"/runs/{run_id}", headers=HEADERS).json()
    return body


def _spend(api: Api, run_id: str, cost: str) -> None:
    api.storage.calls.record(call(run_id=run_id, cost=cost, at=api.clock.now()))


def _taxonomy(api: Api) -> StoredTaxonomy:
    return api.storage.taxonomies.save(
        Taxonomy(industry="cafe", topics=(Topic(key="staff", name="Staff", description=""),))
    )


def _classify(api: Api, taxonomy: StoredTaxonomy, *external_ids: str) -> None:
    topics = [
        ReviewTopic(review_external_id=i, topic_key="staff", sentiment=Sentiment.POSITIVE, confidence=0.9)
        for i in external_ids
    ]
    api.storage.reviews.save_topics(Source.GOOGLE_MAPS, taxonomy, topics)


def test_a_queued_run_has_the_budget_and_nothing_else_known() -> None:
    api = Api(known=[cafe()])
    status = _status(api, _start(api))
    assert status["budget"] == "1"
    assert (status["downloaded"], status["flagged"]) == (None, None)
    assert (status["classified"], status["to_classify"]) == (None, None)
    assert status["step_cost"] == {"downloading": None, "classifying": None, "analysis": None}


def test_downloading_counts_the_reviews_per_source_and_the_flagged_ones() -> None:
    api = Api(known=[cafe()])
    run_id = _start(api)
    api.storage.runs.advance(run_id, RunStatus.DOWNLOADING)
    api.storage.reviews.add([review("r1"), review("r2"), review("r3", flagged=True)])
    _spend(api, run_id, "0.25")
    status = _status(api, run_id)
    assert status["downloaded"] == {"google_maps": 3}
    assert status["flagged"] == 1
    assert (status["classified"], status["to_classify"]) == (None, None)
    assert status["step_cost"] == {"downloading": "0.25", "classifying": None, "analysis": None}


def test_the_classified_count_moves_with_every_batch() -> None:
    api = Api(known=[cafe()])
    run_id = _start(api)
    api.storage.runs.advance(run_id, RunStatus.DOWNLOADING)
    api.storage.reviews.add([review("r1"), review("r2"), review("r3"), review("r4", flagged=True)])
    _spend(api, run_id, "0.25")
    api.advance(MINUTE)
    api.storage.runs.advance(run_id, RunStatus.CLASSIFYING)
    assert (_status(api, run_id)["classified"], _status(api, run_id)["to_classify"]) == (0, 3)
    taxonomy = _taxonomy(api)
    _classify(api, taxonomy, "r1")
    _spend(api, run_id, "0.1")
    assert _status(api, run_id)["classified"] == 1
    _classify(api, taxonomy, "r2", "r3")
    _spend(api, run_id, "0.1")
    status = _status(api, run_id)
    assert (status["classified"], status["to_classify"], status["flagged"]) == (3, 3, 1)
    assert status["step_cost"] == {"downloading": "0.25", "classifying": "0.2", "analysis": None}
    assert status["cost"] == "0.45"


def test_a_review_that_failed_classification_is_not_counted_as_classified() -> None:
    api = Api(known=[cafe()])
    run_id = _start(api)
    api.storage.reviews.add([review("r1")])
    api.storage.runs.advance(run_id, RunStatus.CLASSIFYING)
    failed = ReviewTopic(
        review_external_id="r1", topic_key="unclassified", sentiment=Sentiment.NEUTRAL, confidence=0
    )
    api.storage.reviews.save_topics(Source.GOOGLE_MAPS, _taxonomy(api), [failed])
    assert _status(api, run_id)["classified"] == 0


def test_the_costs_of_all_steps_are_final_after_the_run() -> None:
    api = Api(known=[cafe()])
    run_id = _start(api)
    api.storage.runs.advance(run_id, RunStatus.DOWNLOADING)
    api.storage.reviews.add([review("r1")])
    _spend(api, run_id, "0.25")
    api.advance(MINUTE)
    api.storage.runs.advance(run_id, RunStatus.CLASSIFYING)
    _classify(api, _taxonomy(api), "r1")
    _spend(api, run_id, "0.125")
    api.advance(MINUTE)
    api.storage.runs.advance(run_id, RunStatus.ANALYZING)
    _spend(api, run_id, "0.0625")
    api.advance(MINUTE)
    api.storage.runs.advance(run_id, RunStatus.DONE)
    status = _status(api, run_id)
    assert status["step_cost"] == {"downloading": "0.25", "classifying": "0.125", "analysis": "0.0625"}
    assert Decimal(status["cost"]) == Decimal("0.4375")
    assert (status["classified"], status["to_classify"], status["finished"]) == (1, 1, True)


def test_a_run_that_failed_while_downloading_has_no_classification_counts() -> None:
    api = Api(known=[cafe()])
    run_id = _start(api)
    api.storage.runs.advance(run_id, RunStatus.DOWNLOADING)
    api.storage.runs.advance(run_id, RunStatus.FAILED)
    status = _status(api, run_id)
    assert (status["classified"], status["to_classify"]) == (None, None)
    assert status["downloaded"] == {"google_maps": 0}


def test_the_status_never_carries_review_text() -> None:
    api = Api(known=[cafe()])
    run_id = _start(api)
    api.storage.runs.advance(run_id, RunStatus.DOWNLOADING)
    api.storage.reviews.add([review("r1")])
    assert "Dobrá káva" not in api.client.get(f"/runs/{run_id}", headers=HEADERS).text
