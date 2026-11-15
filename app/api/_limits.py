from collections import defaultdict, deque
from datetime import date, datetime, timedelta

from app.domain import Clock


class SlidingWindow:
    """At most `limit` hits per key within `window`, counted by the Clock."""

    def __init__(self, clock: Clock, limit: int, window: timedelta) -> None:
        self._clock = clock
        self._limit = limit
        self._window = window
        self._hits: dict[str, deque[datetime]] = defaultdict(deque)

    def hit(self, key: str) -> timedelta | None:
        """Count one hit. `None` when allowed, else how long until the key may try again."""
        now = self._clock.now()
        hits = self._hits[key]
        while hits and hits[0] <= now - self._window:
            hits.popleft()
        if len(hits) >= self._limit:
            return hits[0] + self._window - now
        hits.append(now)
        return None


class DailyCounter:
    """At most `limit` counts per key per UTC day."""

    def __init__(self, clock: Clock, limit: int) -> None:
        self._clock = clock
        self._limit = limit
        self._counts: dict[tuple[str, date], int] = defaultdict(int)

    def _today(self) -> date:
        return self._clock.now().date()

    def exhausted(self, key: str) -> bool:
        return self._counts[(key, self._today())] >= self._limit

    def count(self, key: str) -> None:
        self._counts[(key, self._today())] += 1
