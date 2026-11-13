from datetime import date

import pytest

from app.domain import Change, ChangeKind, InsightType, Metrics, Source
from app.insights import MAX_SAMPLE_CHARS, MAX_SAMPLES
from app.llm import InvalidOutput
from tests.insights.helpers import RUN, answer, item, metrics, review, setup

SAMPLES = [review("r1"), review("r2"), review("r3")]


def test_grounded_insights_are_returned_with_their_review_ids() -> None:
    gen, _ = setup(answer(item("Waiting got longer.", ["r1", "r2"], "anomaly")))

    result = gen.generate(metrics(), SAMPLES, run_id=RUN)

    assert [(i.type, i.text, i.review_ids) for i in result.insights] == [
        (InsightType.ANOMALY, "Waiting got longer.", ("r1", "r2"))
    ]
    assert result.dropped == 0
    assert result.fallback_summary is None


def test_an_insight_citing_a_missing_review_is_dropped_and_counted() -> None:
    gen, _ = setup(answer(item("Good.", ["r1"]), item("Invented.", ["r1", "r999"], "suggestion")))

    result = gen.generate(metrics(), SAMPLES, run_id=RUN)

    assert [i.text for i in result.insights] == ["Good."]
    assert result.dropped == 1
    assert result.fallback_summary is None


def test_an_insight_without_review_ids_is_dropped() -> None:
    gen, _ = setup(answer(item("Good.", ["r1"]), item("No evidence.", [])))

    result = gen.generate(metrics(), SAMPLES, run_id=RUN)

    assert [i.text for i in result.insights] == ["Good."]
    assert result.dropped == 1


def test_a_review_the_prompt_never_showed_does_not_ground_an_insight() -> None:
    gen, _ = setup(answer(item("Flagged one.", ["rf"])))

    result = gen.generate(metrics(), [review("r1"), review("rf", flagged=True)], run_id=RUN)

    assert result.insights == ()
    assert result.dropped == 1


def test_when_everything_is_dropped_the_summary_comes_from_the_metrics() -> None:
    gen, _ = setup(answer(item("Invented.", ["nope"])))

    result = gen.generate(metrics(), SAMPLES, run_id=RUN)

    assert result.insights == ()
    assert result.dropped == 1
    assert result.fallback_summary == (
        "Average rating 3.4 from 10 reviews. 1 drop and 0 rises detected; "
        "the biggest change is -0.8 stars on google_maps in 2026-10 (waiting)."
    )


def test_the_fallback_summary_is_deterministic() -> None:
    first = setup(answer())[0].generate(metrics(), SAMPLES, run_id=RUN)
    second = setup(answer())[0].generate(metrics(), SAMPLES, run_id=RUN)

    assert first.fallback_summary == second.fallback_summary
    assert first.fallback_summary is not None


def test_an_empty_answer_gives_the_fallback_summary() -> None:
    gen, _ = setup(answer())

    result = gen.generate(metrics(), SAMPLES, run_id=RUN)

    assert result.dropped == 0
    assert result.fallback_summary is not None


def test_no_reviews_at_all_gives_a_fallback_and_asks_no_model() -> None:
    gen, completer = setup()

    result = gen.generate(Metrics(trend=(), topic_shares=(), changes=()), [], run_id=RUN)

    assert completer.calls == []
    assert result.fallback_summary == "No reviews to summarise."


def test_a_model_error_passes_through() -> None:
    gen, _ = setup(RuntimeError("provider down"))

    try:
        gen.generate(metrics(), SAMPLES, run_id=RUN)
    except RuntimeError as error:
        assert str(error) == "provider down"
    else:
        raise AssertionError("the error was swallowed")


def test_the_sample_is_bounded() -> None:
    many = [review(f"r{n}") for n in range(MAX_SAMPLES + 25)]
    gen, completer = setup(answer(item("Late one.", [f"r{MAX_SAMPLES + 5}"])))

    result = gen.generate(metrics(), many, run_id=RUN)

    assert completer.calls[0].prompt.count("<review ") == MAX_SAMPLES
    # An ID beyond the bound was never shown, so it cannot ground an Insight.
    assert result.insights == ()
    assert result.dropped == 1


def test_a_long_review_text_is_cut() -> None:
    gen, completer = setup(answer())

    gen.generate(metrics(), [review("r1", "x" * (MAX_SAMPLE_CHARS + 500))], run_id=RUN)

    assert "x" * MAX_SAMPLE_CHARS in completer.calls[0].prompt
    assert "x" * (MAX_SAMPLE_CHARS + 1) not in completer.calls[0].prompt


def test_a_malformed_insight_is_dropped_and_counted() -> None:
    bad_date = item("Bad date.", ["r1"]) | {"period_start": "last october"}
    backwards = item("Backwards.", ["r1"]) | {"period_start": "2026-11-01", "period_end": "2026-10-01"}
    gen, _ = setup(answer(item("Good.", ["r1"]), bad_date, backwards, item("   ", ["r1"])))

    result = gen.generate(metrics(), SAMPLES, run_id=RUN)

    assert [i.text for i in result.insights] == ["Good."]
    assert result.dropped == 3


def test_invalid_json_from_the_model_raises_invalid_output() -> None:
    gen, _ = setup("not json")

    with pytest.raises(InvalidOutput):
        gen.generate(metrics(), SAMPLES, run_id=RUN)


def test_the_fallback_without_any_change_says_so() -> None:
    quiet = metrics().model_copy(update={"changes": ()})
    gen, _ = setup(answer())

    result = gen.generate(quiet, SAMPLES, run_id=RUN)

    assert result.fallback_summary == "Average rating 3.4 from 10 reviews. No drops or rises detected."


def test_the_fallback_names_the_biggest_of_several_changes() -> None:
    base = metrics()
    rise = Change(kind=ChangeKind.RISE, source=Source.FIRMY_CZ, period_start=date(2026, 9, 1), delta=0.6)
    two = base.model_copy(update={"changes": (*base.changes, rise)})
    gen, _ = setup(answer())

    result = gen.generate(two, SAMPLES, run_id=RUN)

    assert result.fallback_summary == (
        "Average rating 3.4 from 10 reviews. 1 drop and 1 rise detected; "
        "the biggest change is -0.8 stars on google_maps in 2026-10 (waiting)."
    )
