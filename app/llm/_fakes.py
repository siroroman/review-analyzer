from datetime import timedelta

from app.domain import FakeClock
from app.llm._types import TraceEvent


class FakeSleeper:
    """A Sleeper that moves a FakeClock instead of waiting, and remembers each delay."""

    def __init__(self, clock: FakeClock) -> None:
        self._clock = clock
        self.delays: list[timedelta] = []

    def sleep(self, delay: timedelta) -> None:
        self.delays.append(delay)
        self._clock.advance(delay)


class FakeTracer:
    """A Tracer that remembers the events it got."""

    def __init__(self) -> None:
        self.events: list[TraceEvent] = []

    def trace(self, event: TraceEvent) -> None:
        self.events.append(event)
