import pytest

from app.llm import Route, UnknownTask
from tests.llm.helpers import (
    CHAT_USAGE,
    SECOND,
    VALID,
    Answer,
    Setup,
    requests,
    scripted,
)


def test_complete_returns_the_answer_as_the_schema_type() -> None:
    s = Setup()

    result = s.llm.complete("classify", "Rate this.", Answer, run_id="run-1")

    assert result == Answer(label="service", score=3)


def test_a_task_goes_to_the_model_of_its_route() -> None:
    s = Setup()

    s.llm.complete("classify", "Rate this.", Answer, run_id="run-1")
    s.llm.complete("insights", "Summarise.", Answer, run_id="run-1")

    assert [r.model for r in requests(s.openrouter)] == ["jev-1.14"]
    assert [r.model for r in requests(s.chat)] == ["deepseek-alt"]


def test_the_routing_table_is_configuration() -> None:
    s = Setup(routes={"classify": Route(SECOND)})

    s.llm.complete("classify", "Rate this.", Answer, run_id="run-1")

    assert [r.model for r in requests(s.chat)] == ["deepseek-alt"]
    assert requests(s.openrouter) == []


def test_a_task_without_a_route_is_an_error_and_calls_nothing() -> None:
    s = Setup()

    with pytest.raises(UnknownTask):
        s.llm.complete("translate", "Hi", Answer, run_id="run-1")

    assert s.log.calls == []


def test_the_request_carries_the_prompt_the_system_prompt_and_the_schema() -> None:
    s = Setup()

    s.llm.complete("classify", "Rate this.", Answer, run_id="run-1", system="You rate reviews.")

    [request] = requests(s.openrouter)
    assert (request.prompt, request.system) == ("Rate this.", "You rate reviews.")
    assert request.json_schema["required"] == ["label", "score"]


def test_the_system_prompt_is_cached_only_when_asked() -> None:
    s = Setup(chat=lambda clock: scripted(CHAT_USAGE, VALID, VALID, clock=clock))

    s.llm.complete("insights", "a", Answer, run_id="run-1", system="S")
    s.llm.complete("insights", "b", Answer, run_id="run-1", system="S", cache_system=True)

    assert [r.cache_system for r in requests(s.chat)] == [False, True]
