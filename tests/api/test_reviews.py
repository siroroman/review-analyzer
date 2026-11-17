from datetime import date

from httpx import Response

from app.domain import ReviewTopic, Sentiment, Source, Taxonomy, Topic
from tests.api.helpers import HEADERS, Api, cafe
from tests.storage.helpers import review

RUN = {"place_ids": ["g1"]}


def _api_with_reviews() -> tuple[Api, str]:
    api = Api(known=[cafe()])
    run_id = str(api.client.post("/runs", json=RUN, headers=HEADERS).json()["run_id"])
    company_id = api.storage.runs.get(run_id).company_id  # type: ignore[union-attr]
    api.storage.companies.set_industry(company_id, "cafe")
    api.storage.reviews.add(
        [
            review("r1", "g1", published_on=date(2026, 10, 1)),
            review("r2", "g1", published_on=date(2026, 10, 5)),
            review("r3", "g1", published_on=date(2026, 10, 3)),
            review("secret", "g1", flagged=True),
        ]
    )
    stored = api.storage.taxonomies.save(
        Taxonomy(industry="cafe", topics=(Topic(key="staff", name="Obsluha", description="x"),))
    )
    topics = [
        ReviewTopic(review_external_id=i, topic_key="staff", sentiment=Sentiment.NEGATIVE, confidence=0.9)
        for i in ("r1", "r3", "secret")
    ]
    api.storage.reviews.save_topics(Source.GOOGLE_MAPS, stored, topics)
    return api, run_id


def _get(api: Api, run_id: str, query: str) -> Response:
    response: Response = api.client.get(f"/runs/{run_id}/reviews?{query}", headers=HEADERS)
    return response


def test_reviews_by_ids_carry_source_place_name_rating_date_and_text() -> None:
    api, run_id = _api_with_reviews()
    response = _get(api, run_id, "ids=r1")
    assert response.status_code == 200
    assert response.json() == [
        {
            "id": "r1",
            "source": "google_maps",
            "place_name": "Kavárna",
            "rating": 4,
            "date": "2026-10-01",
            "text": "Dobrá káva, pomalá obsluha.",
        }
    ]


def test_reviews_by_ids_skip_unknown_ids_and_flagged_reviews() -> None:
    api, run_id = _api_with_reviews()
    found = _get(api, run_id, "ids=r1&ids=nope&ids=secret").json()
    assert [r["id"] for r in found] == ["r1"]


def test_reviews_of_another_runs_company_are_not_returned() -> None:
    api, run_id = _api_with_reviews()
    api.setup.google.known["g9"] = cafe("g9")
    other = str(api.client.post("/runs", json={"place_ids": ["g9"]}, headers=HEADERS).json()["run_id"])
    api.storage.companies.set_industry(api.storage.runs.get(other).company_id, "cafe")  # type: ignore[union-attr]
    assert _get(api, other, "ids=r1").json() == []
    assert [r["id"] for r in _get(api, run_id, "ids=r1").json()] == ["r1"]


def test_reviews_by_topic_are_the_ones_with_that_topic_newest_first_without_flagged() -> None:
    api, run_id = _api_with_reviews()
    found = _get(api, run_id, "topic=staff").json()
    assert [r["id"] for r in found] == ["r3", "r1"]
    assert "secret" not in str(found)


def test_an_unknown_topic_has_no_reviews() -> None:
    api, run_id = _api_with_reviews()
    assert _get(api, run_id, "topic=nope").json() == []


def test_ids_and_topic_together_or_neither_are_422() -> None:
    api, run_id = _api_with_reviews()
    assert _get(api, run_id, "ids=r1&topic=staff").status_code == 422
    assert _get(api, run_id, "").status_code == 422


def test_too_many_ids_are_422() -> None:
    api, run_id = _api_with_reviews()
    query = "&".join(f"ids=r{i}" for i in range(101))
    assert _get(api, run_id, query).status_code == 422


def test_reviews_of_an_unknown_run_are_404() -> None:
    api, _ = _api_with_reviews()
    assert _get(api, "nope", "ids=r1").status_code == 404


def test_reviews_need_a_demo_token() -> None:
    api, run_id = _api_with_reviews()
    assert api.client.get(f"/runs/{run_id}/reviews?ids=r1").status_code == 401


def test_reviews_by_topic_are_cut_at_200() -> None:
    api, run_id = _api_with_reviews()
    many = [review(f"m{i}", "g1") for i in range(250)]
    api.storage.reviews.add(many)
    stored = api.storage.taxonomies.latest("cafe")
    assert stored is not None
    api.storage.reviews.save_topics(
        Source.GOOGLE_MAPS,
        stored,
        [
            ReviewTopic(
                review_external_id=r.external_id,
                topic_key="staff",
                sentiment=Sentiment.NEGATIVE,
                confidence=0.9,
            )
            for r in many
        ],
    )
    assert len(_get(api, run_id, "topic=staff").json()) == 200
