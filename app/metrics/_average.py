from collections.abc import Sequence


def average_rating(ratings: Sequence[int]) -> float:
    if not ratings:
        raise ValueError("no ratings to average")
    if any(not 1 <= r <= 5 for r in ratings):
        raise ValueError("a rating must be between 1 and 5")
    return sum(ratings) / len(ratings)
