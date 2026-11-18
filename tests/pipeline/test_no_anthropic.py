"""No Anthropic model anywhere in the product (#134): not in the source, not in a Run."""

import re
from pathlib import Path

from app.domain import RunStatus
from app.storage import CallFilter
from tests.pipeline.helpers import World

ROOT = Path(__file__).parents[2]
_FORBIDDEN = re.compile(r"anthropic|claude|haiku|sonnet", re.IGNORECASE)


def test_no_source_file_of_the_product_names_an_anthropic_model() -> None:
    sources = [*(ROOT / "app").rglob("*.py"), *(ROOT / "evaluation").rglob("*.py")]
    assert sources
    named = [str(path.relative_to(ROOT)) for path in sources if _FORBIDDEN.search(path.read_text())]
    assert named == []


def test_a_run_over_a_gateway_that_does_not_know_anthropic_finishes_and_calls_only_openrouter() -> None:
    # The gateway of the World allows `openrouter` and `openrouter_chat` only: an `anthropic` call
    # would be denied and show up in the Call log as such.
    world = World()
    result = world.run()
    assert result.status is RunStatus.DONE
    calls = world.storage.calls.query(CallFilter())
    assert {call.service for call in calls if call.operation == "complete"} == {
        "openrouter",
        "openrouter_chat",
    }
    assert all(call.status != "denied" for call in calls)
