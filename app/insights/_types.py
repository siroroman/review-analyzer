from dataclasses import dataclass
from typing import Protocol

from pydantic import BaseModel

from app.domain import Insight


@dataclass(frozen=True)
class Insights:
    """What `generate` returns: the Insights that passed both checks and what the checks cost.

    `dropped` counts Insights that failed Grounding (a Review ID that was not in the sample, no ID at
    all) or that were malformed. `removed` counts Insights the content check removed (personal data,
    insults). `fallback_summary` is set when no Insight is left: a deterministic text from Metrics.
    """

    insights: tuple[Insight, ...]
    dropped: int
    removed: int
    fallback_summary: str | None


class Completer(Protocol):
    """The part of `llm.Llm` that `insights` uses."""

    def complete[T: BaseModel](
        self,
        task: str,
        prompt: str,
        schema: type[T],
        *,
        run_id: str,
        system: str | None = None,
        cache_system: bool = False,
    ) -> T: ...
