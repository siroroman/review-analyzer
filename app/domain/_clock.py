from datetime import datetime, timedelta
from typing import Protocol


class Clock(Protocol):
    """The only source of the current time in `app/` (ADR-0004)."""

    def now(self) -> datetime:
        """The current time, always with a time zone."""
        ...


class FakeClock:
    """A Clock that moves only when a test advances it. Tests never sleep and never read the real time."""

    def __init__(self, start: datetime) -> None:
        if start.tzinfo is None:
            raise ValueError("FakeClock needs a time with a time zone")
        self._now = start

    def now(self) -> datetime:
        return self._now

    def advance(self, by: timedelta) -> None:
        if by < timedelta(0):
            raise ValueError("a clock does not go backwards")
        self._now += by
