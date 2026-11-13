from collections.abc import Sequence

from app.domain import Metrics, Review
from app.insights import _checks, _prompt
from app.insights._types import Completer, Insights

_TASK = "insights"


class InsightGenerator:
    """Turns Metrics and a bounded sample of Reviews into Insights the model could not make up.

    The model sees Metrics and at most `MAX_SAMPLES` unflagged Reviews, each delimited as data with
    its ID. Its answer then passes Grounding and the content check. Errors of the model call
    (`InvalidOutput`, `BudgetExceeded`, provider errors) pass through unchanged.
    """

    def __init__(self, llm: Completer) -> None:
        self._llm = llm

    def generate(self, metrics: Metrics, samples: Sequence[Review], *, run_id: str) -> Insights:
        shown = _prompt.sample_of(samples)
        if not shown:
            return Insights(
                insights=(), dropped=0, removed=0, fallback_summary=_checks.fallback_summary(metrics)
            )
        answer = self._llm.complete(
            _TASK,
            _prompt.build(metrics, shown),
            _prompt.ModelAnswer,
            run_id=run_id,
            system=_prompt.SYSTEM,
            cache_system=True,
        )
        grounded, dropped = _checks.ground(answer.insights, {r.external_id for r in shown})
        clean, removed = _checks.content_check(grounded)
        return Insights(
            insights=tuple(clean),
            dropped=dropped,
            removed=removed,
            fallback_summary=None if clean else _checks.fallback_summary(metrics),
        )
