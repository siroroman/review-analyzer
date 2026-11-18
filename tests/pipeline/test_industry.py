from datetime import timedelta

from app.domain import RunStatus
from app.gateway import ClientError
from app.pipeline import NOTE_INDUSTRY_FALLBACK
from app.storage import CallFilter
from app.taxonomy import GENERIC_INDUSTRY
from tests.pipeline.helpers import INJECTION, World, month_of_reviews, with_injection


def stored_industry(world: World) -> str | None:
    stored = world.storage.companies.by_id(world.company.id)
    assert stored is not None
    return stored.company.industry


def test_the_industry_is_inferred_after_the_download_and_stored_on_the_company() -> None:
    world = World(industry=None, industry_answer='{"label": "Coffee Shop"}')
    result = world.run()
    assert result.status is RunStatus.DONE
    assert stored_industry(world) == "coffee-shop"
    assert world.storage.taxonomies.latest("coffee-shop") is not None
    assert world.model_calls_of("industry") == 1
    assert result.notes == ()


def test_an_inferred_industry_is_not_inferred_again_by_the_next_run() -> None:
    world = World(industry=None)
    world.run()
    world.run()
    assert world.model_calls_of("industry") == 1


def test_a_known_industry_costs_no_inference() -> None:
    world = World(industry="gym")
    world.run()
    assert world.model_calls_of("industry") == 0


def test_an_industry_with_a_frozen_taxonomy_reuses_it() -> None:
    world = World(industry=None)
    world.run()
    other = World(industry=None)
    other.storage.taxonomies.save(world.storage.taxonomies.latest("cafe").taxonomy)  # type: ignore[union-attr]
    other.run()
    assert other.model_calls_of("taxonomy") == 0
    assert other.storage.taxonomies.get("cafe", 2) is None


def test_the_inference_counts_in_the_cost_of_the_run_and_in_the_call_log() -> None:
    world = World(industry=None)
    with_inference = world.run()
    known = World(industry="cafe").run()
    assert with_inference.cost > known.cost
    logged = world.storage.calls.query(CallFilter(run_id=with_inference.run_id))
    assert len([c for c in logged if c.service in ("openrouter", "openrouter_chat")]) == len(
        world.model_calls
    )
    assert "industry" in world.model_calls


def test_an_invalid_answer_falls_back_to_the_generic_industry_and_says_so() -> None:
    world = World(industry=None, industry_answer='{"label": "???"}')
    result = world.run()
    assert result.status is RunStatus.DONE
    assert stored_industry(world) == GENERIC_INDUSTRY
    assert world.storage.taxonomies.latest(GENERIC_INDUSTRY) is not None
    assert result.notes == (NOTE_INDUSTRY_FALLBACK,)
    assert world.pipeline.report(result.run_id).result.notes == (NOTE_INDUSTRY_FALLBACK,)


def test_a_model_error_falls_back_to_the_generic_industry() -> None:
    world = World(industry=None, always_fail={"industry": ClientError("rejected")})
    result = world.run()
    assert result.status is RunStatus.DONE
    assert stored_industry(world) == GENERIC_INDUSTRY
    assert result.notes == (NOTE_INDUSTRY_FALLBACK,)


def test_too_few_reviews_fall_back_to_the_generic_industry_without_a_call() -> None:
    world = World(industry=None, scraped_reviews=month_of_reviews(5))
    result = world.run()
    assert world.model_calls_of("industry") == 0
    assert stored_industry(world) == GENERIC_INDUSTRY
    assert result.notes == (NOTE_INDUSTRY_FALLBACK,)


def test_a_generic_industry_is_inferred_again_by_the_next_run() -> None:
    world = World(industry=None, industry_answer='{"label": "???"}')
    world.run()
    world.industry_answer = '{"label": "cafe"}'
    world.clock.advance(timedelta(days=2))  # past the cache, so the next Run does the work again
    result = world.run()
    assert stored_industry(world) == "cafe"
    assert result.notes == ()


def test_an_exceeded_budget_still_ends_the_run_as_partial() -> None:
    world = World(industry=None, big=frozenset({"industry"}))
    result = world.run()
    assert result.status is RunStatus.PARTIAL
    assert stored_industry(world) is None


def test_flagged_reviews_never_reach_the_industry_prompt() -> None:
    world = World(industry=None, scraped_reviews=with_injection(month_of_reviews(40)))
    world.run()
    assert INJECTION not in world.prompts["industry"]


def test_a_fallback_run_keeps_its_note_after_a_later_run_infers_a_real_industry() -> None:
    world = World(industry=None, industry_answer='{"label": "???"}')
    first = world.run()
    world.industry_answer = '{"label": "cafe"}'
    world.clock.advance(timedelta(days=2))
    second = world.run()
    assert second.notes == ()
    assert world.pipeline.report(first.run_id).result.notes == (NOTE_INDUSTRY_FALLBACK,)
    assert world.pipeline.run(first.run_id).notes == (NOTE_INDUSTRY_FALLBACK,)
