import random  # noqa: TID251 - this module is the RandomSource adapter and its fake
from collections.abc import Sequence
from typing import Protocol, TypeVar

T = TypeVar("T")


class RandomSource(Protocol):
    """The only source of randomness in `app/` (ADR-0004)."""

    def sample(self, items: Sequence[T], count: int) -> list[T]:
        """`count` distinct items chosen at random, or all of them when there are fewer."""
        ...


class SystemRandom:
    """The real `RandomSource`: the one place that draws from the randomness of the machine."""

    def __init__(self) -> None:
        self._random = random.SystemRandom()  # noqa: TID251 - this is the RandomSource adapter itself

    def sample(self, items: Sequence[T], count: int) -> list[T]:
        return self._random.sample(list(items), min(count, len(items)))


class SeededRandom:
    """A RandomSource that repeats itself for one seed. Tests never draw real randomness."""

    def __init__(self, seed: int) -> None:
        self._random = random.Random(seed)  # noqa: TID251, S311 - this is the RandomSource fake itself

    def sample(self, items: Sequence[T], count: int) -> list[T]:
        return self._random.sample(list(items), min(count, len(items)))
