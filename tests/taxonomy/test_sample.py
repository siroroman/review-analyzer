"""The sample of Reviews a Taxonomy is generated from: at most MAX_SAMPLE, random, reproducible."""

import json
import re
from collections.abc import Sequence

from app.domain import Review, SeededRandom
from app.llm import ModelRef, Route
from app.storage import in_memory_storage
from app.taxonomy import MAX_SAMPLE, MIN_SAMPLE, Taxonomies
from tests.llm.helpers import HAIKU_USAGE, Setup, requests, scripted
from tests.taxonomy.test_get_taxonomy import reviews, topics_json

ROUTES = {"taxonomy": Route(ModelRef("anthropic", "claude-haiku"))}


def numbered(count: int, *, text_from: int = 0, flagged_from: int | None = None) -> list[Review]:
    """Reviews with texts `review-<i>`; the first `text_from` have none, later ones are Flagged."""
    return [
        r.model_copy(
            update={
                "text": f"review-{i}" if i >= text_from else "",
                "flagged": flagged_from is not None and i >= flagged_from,
            }
        )
        for i, r in enumerate(reviews(count))
    ]


def texts_sent(found: Sequence[Review], seed: int) -> list[str]:
    setup = Setup(haiku=lambda clock: scripted(HAIKU_USAGE, topics_json(8), clock=clock), routes=ROUTES)
    taxonomies = Taxonomies(setup.llm, in_memory_storage(setup.clock).taxonomies, SeededRandom(seed))
    taxonomies.get_taxonomy("cafe", sample=lambda: found, run_id="run-1")
    prompt = requests(setup.anthropic)[0].prompt
    texts: list[str] = json.loads(prompt.split("<reviews>\n")[1].split("\n</reviews>")[0])
    return texts


def test_the_sample_has_at_most_200_reviews_all_with_text_and_none_flagged() -> None:
    # 1000 Reviews: 600 without text; of the 400 with text the last 50 are Flagged.
    found = numbered(1000, text_from=600, flagged_from=950)
    sent = texts_sent(found, seed=1)
    assert MAX_SAMPLE == 200
    assert len(sent) == 200
    numbers = [int(re.fullmatch(r"review-(\d+)", t).group(1)) for t in sent]  # type: ignore[union-attr]
    assert all(600 <= n < 950 for n in numbers)
    assert len(set(numbers)) == 200


def test_fewer_reviews_with_text_than_the_cap_are_all_in_the_sample() -> None:
    found = numbered(MIN_SAMPLE + 20, text_from=10)
    assert sorted(texts_sent(found, seed=1)) == sorted(f"review-{i}" for i in range(10, MIN_SAMPLE + 20))


def test_the_same_seed_gives_the_same_sample_whatever_the_order_of_the_input() -> None:
    found = numbered(500)
    assert texts_sent(found, seed=7) == texts_sent(found, seed=7)
    assert texts_sent(found, seed=7) == texts_sent(list(reversed(found)), seed=7)


def test_another_seed_gives_another_sample() -> None:
    found = numbered(500)
    assert texts_sent(found, seed=1) != texts_sent(found, seed=2)
