from datetime import UTC, datetime, timedelta

import pytest

from app.domain import Clock, FakeClock


def test_fake_clock_returns_the_time_it_was_given() -> None:
    clock = FakeClock(datetime(2026, 11, 12, 8, 0, tzinfo=UTC))

    assert clock.now() == datetime(2026, 11, 12, 8, 0, tzinfo=UTC)


def test_fake_clock_moves_only_when_advanced() -> None:
    clock = FakeClock(datetime(2026, 11, 12, 8, 0, tzinfo=UTC))

    clock.advance(timedelta(hours=25))

    assert clock.now() == datetime(2026, 11, 13, 9, 0, tzinfo=UTC)


def test_fake_clock_is_a_clock() -> None:
    clock: Clock = FakeClock(datetime(2026, 1, 1, tzinfo=UTC))

    assert clock.now().tzinfo is not None


def test_fake_clock_rejects_a_time_without_a_zone() -> None:
    with pytest.raises(ValueError, match="time zone"):
        FakeClock(datetime(2026, 11, 12, 8, 0))


def test_fake_clock_rejects_going_back() -> None:
    clock = FakeClock(datetime(2026, 11, 12, 8, 0, tzinfo=UTC))

    with pytest.raises(ValueError, match="backwards"):
        clock.advance(timedelta(seconds=-1))
