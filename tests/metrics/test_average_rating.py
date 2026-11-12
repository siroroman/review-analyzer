import pytest
from hypothesis import given
from hypothesis import strategies as st

from app.metrics import average_rating


def test_average_of_a_worked_example() -> None:
    assert average_rating([5, 4, 3, 4]) == 4.0


def test_average_keeps_the_fraction() -> None:
    assert average_rating([5, 4]) == 4.5


def test_average_of_no_ratings_is_an_error() -> None:
    with pytest.raises(ValueError, match="no ratings"):
        average_rating([])


@pytest.mark.parametrize("bad", [0, 6, -1])
def test_a_rating_outside_one_to_five_is_an_error(bad: int) -> None:
    with pytest.raises(ValueError, match="between 1 and 5"):
        average_rating([5, bad])


@given(st.lists(st.integers(min_value=1, max_value=5), min_size=1))
def test_average_stays_within_the_ratings(ratings: list[int]) -> None:
    assert min(ratings) <= average_rating(ratings) <= max(ratings)
