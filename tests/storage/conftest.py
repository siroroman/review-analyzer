from collections.abc import Iterator

import pytest

from app.domain import FakeClock
from app.storage import Storage, in_memory_storage
from tests.storage.helpers import START


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock(START)


@pytest.fixture(params=["memory"])
def storage(request: pytest.FixtureRequest, clock: FakeClock) -> Iterator[Storage]:
    """Every contract test runs on every implementation of the repositories."""
    yield in_memory_storage(clock)
