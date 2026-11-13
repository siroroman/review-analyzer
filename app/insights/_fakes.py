from dataclasses import dataclass

from pydantic import BaseModel, ValidationError

from app.llm import InvalidOutput


@dataclass(frozen=True)
class CompleterCall:
    """One request a FakeCompleter received."""

    task: str
    prompt: str
    system: str | None
    cache_system: bool
    run_id: str


class FakeCompleter:
    """A Completer that plays scripted steps in order and remembers what it was asked.

    A string step is the model's raw JSON answer, validated against the schema like the real Llm does
    (invalid JSON raises `InvalidOutput`); an exception step is raised.
    """

    def __init__(self, *steps: str | Exception) -> None:
        self._steps = list(steps)
        self.calls: list[CompleterCall] = []

    def complete[T: BaseModel](
        self,
        task: str,
        prompt: str,
        schema: type[T],
        *,
        run_id: str,
        system: str | None = None,
        cache_system: bool = False,
    ) -> T:
        self.calls.append(CompleterCall(task, prompt, system, cache_system, run_id))
        step = self._steps.pop(0)
        if isinstance(step, Exception):
            raise step
        try:
            return schema.model_validate_json(step)
        except ValidationError:
            raise InvalidOutput(task, "fake") from None
