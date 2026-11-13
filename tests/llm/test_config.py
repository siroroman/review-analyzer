from datetime import timedelta

import pytest

from app.llm import LlmConfig


def test_a_negative_retry_count_is_rejected() -> None:
    with pytest.raises(ValueError, match="negative"):
        LlmConfig(routes={}, max_retries=-1)


def test_a_negative_backoff_is_rejected() -> None:
    with pytest.raises(ValueError, match="negative"):
        LlmConfig(routes={}, backoff=timedelta(seconds=-1))
