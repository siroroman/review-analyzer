from dataclasses import dataclass, field
from datetime import timedelta
from decimal import Decimal

from app.domain import RunStatus, Source


@dataclass(frozen=True)
class PipelineConfig:
    """What `pipeline` reads from configuration.

    `reviews_per_place` is the most Reviews fetched per Place and Run (ADR-0005 input limit). A Run younger
    than `cache_ttl` is reused. A step that fails with one of `retryable_kinds` is attempted at most
    `max_attempts` times; the delay before attempt n + 1 is `retry_delay * 2 ** (n - 1)`.
    `sources` are the Sources a Run downloads from; Places of any other Source are skipped.
    """

    reviews_per_place: int
    cache_ttl: timedelta = timedelta(hours=24)
    max_attempts: int = 2
    retry_delay: timedelta = timedelta(seconds=5)
    sources: frozenset[Source] = frozenset({Source.GOOGLE_MAPS})
    retryable_kinds: frozenset[str] = field(default_factory=lambda: frozenset({"timeout", "server_error"}))

    def __post_init__(self) -> None:
        if self.reviews_per_place < 1 or self.max_attempts < 1:
            raise ValueError("reviews_per_place and max_attempts must be at least 1")
        if self.retry_delay < timedelta(0) or self.cache_ttl <= timedelta(0):
            raise ValueError("retry_delay must not be negative and cache_ttl must be positive")


@dataclass(frozen=True)
class RunResult:
    """What a Run produced, read from storage, so a redelivered Run returns the same result.

    `reviews` counts every stored Review of the Company, `flagged` the Flagged ones. `unclassified` counts
    unflagged Reviews with no real Topic, for any reason. `cost` is the sum of the Run's Service calls.
    """

    run_id: str
    status: RunStatus
    reviews: int
    flagged: int
    unclassified: int
    insights: int
    trend_points: int
    cost: Decimal
