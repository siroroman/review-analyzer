from datetime import date

import pytest
from hypothesis import given
from hypothesis import strategies as st
from pydantic import ValidationError

from app.domain import DatePrecision, RawReview, Review, Source, TrendPoint


def _review(**changes: object) -> Review:
    fields: dict[str, object] = {
        "source": Source.GOOGLE_MAPS,
        "place_external_id": "ChIJ1",
        "external_id": "rev-1",
        "rating": 4,
        "text": "Rychlá obsluha.",
        "published_on": date(2026, 3, 14),
        "date_precision": DatePrecision.DAY,
        "language": "cs",
        "text_hash": "abc123",
        "flagged": False,
    }
    return Review.model_validate(fields | changes)


def _raw(**changes: object) -> RawReview:
    fields: dict[str, object] = {
        "source": Source.FIRMY_CZ,
        "place_external_id": "f-9",
        "external_id": "r-7",
        "rating": 2,
        "text": "",
        "published_on": date(2026, 1, 5),
        "date_precision": DatePrecision.MONTH,
        "language": None,
    }
    return RawReview.model_validate(fields | changes)


def test_review_round_trips_through_json() -> None:
    review = _review()

    assert Review.model_validate_json(review.model_dump_json()) == review


def test_review_json_has_no_author_field() -> None:
    assert set(_review().model_dump(mode="json")) == {
        "source",
        "place_external_id",
        "external_id",
        "rating",
        "text",
        "published_on",
        "date_precision",
        "language",
        "text_hash",
        "flagged",
    }


def test_review_json_uses_iso_date_and_plain_enums() -> None:
    dumped = _review().model_dump(mode="json")

    assert dumped["published_on"] == "2026-03-14"
    assert dumped["date_precision"] == "day"


@given(rating=st.integers(min_value=1, max_value=5))
def test_review_accepts_ratings_one_to_five(rating: int) -> None:
    assert _review(rating=rating).rating == rating


@given(rating=st.integers().filter(lambda value: not 1 <= value <= 5))
def test_review_rejects_ratings_outside_one_to_five(rating: int) -> None:
    with pytest.raises(ValidationError):
        _review(rating=rating)


def test_review_rejects_a_fractional_rating() -> None:
    with pytest.raises(ValidationError):
        _review(rating=4.5)


@pytest.mark.parametrize("text", ["", "   \n\t"])
def test_review_rejects_empty_text(text: str) -> None:
    with pytest.raises(ValidationError):
        _review(text=text)


def test_review_rejects_an_empty_external_id() -> None:
    with pytest.raises(ValidationError):
        _review(external_id="")


def test_review_rejects_an_unknown_field_such_as_an_author() -> None:
    with pytest.raises(ValidationError):
        _review(author="Jan Novák")


def test_raw_review_may_have_empty_text() -> None:
    assert _raw().text == ""


def test_raw_review_round_trips_through_json() -> None:
    raw = _raw()

    assert RawReview.model_validate_json(raw.model_dump_json()) == raw


def test_raw_review_rejects_a_rating_outside_one_to_five() -> None:
    with pytest.raises(ValidationError):
        _raw(rating=0)


@pytest.mark.parametrize("rating", [True, False, "4", 4.0])
def test_review_rejects_a_rating_that_is_not_an_int(rating: object) -> None:
    with pytest.raises(ValidationError):
        _review(rating=rating)


@pytest.mark.parametrize("flagged", ["no", "yes", "false", 0, 1])
def test_review_rejects_a_flagged_that_is_not_a_bool(flagged: object) -> None:
    with pytest.raises(ValidationError):
        _review(flagged=flagged)


@pytest.mark.parametrize("count", [True, "3", 3.0])
def test_trend_point_rejects_a_count_that_is_not_an_int(count: object) -> None:
    with pytest.raises(ValidationError):
        TrendPoint(
            source=Source.GOOGLE_MAPS,
            period_start=date(2026, 3, 1),
            average_rating=4.0,
            count=count,  # type: ignore[arg-type]
            sentiment=0.0,
        )
