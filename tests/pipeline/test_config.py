from datetime import timedelta

import pytest

from app.pipeline import PipelineConfig


@pytest.mark.parametrize(
    "bad",
    [
        {"reviews_per_place": 0},
        {"reviews_per_place": 10, "max_attempts": 0},
        {"reviews_per_place": 10, "retry_delay": timedelta(seconds=-1)},
        {"reviews_per_place": 10, "cache_ttl": timedelta(0)},
    ],
)
def test_a_nonsensical_config_is_refused(bad: dict[str, object]) -> None:
    with pytest.raises(ValueError):
        PipelineConfig(**bad)  # type: ignore[arg-type]
