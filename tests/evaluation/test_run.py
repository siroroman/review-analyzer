import json
from pathlib import Path

import pytest

from evaluation import EvaluationSet, Report, load_set, main, run_evaluation
from tests.classification.helpers import setup
from tests.llm.helpers import Setup

DATA = Path("evaluation/data")


KEYS = ("staff", "waiting", "prices", "food")


def judgement(expected: dict[str, str]) -> str:
    """What Jev answers for one Review of the sample Taxonomy: a score and a sentiment per Topic."""
    fields: dict[str, object] = {}
    for key in KEYS:
        fields[f"topic_{key}"] = 0.9 if key in expected else 0
        fields[f"sentiment_{key}"] = expected.get(key, "neutral")
    return json.dumps(fields)


def perfect(loaded: EvaluationSet) -> list[str]:
    """The answers a perfect classifier gives: one per Review, in order."""
    return [
        judgement({e.topic: e.sentiment for e in item.expected if e.topic != "unclassified"})
        for item in loaded.items
    ]


def sample() -> EvaluationSet:
    return load_set(DATA / "sample.jsonl", DATA / "sample-taxonomy.json")


def test_a_perfect_classifier_scores_one_everywhere() -> None:
    loaded = sample()
    world: Setup = setup(perfect(loaded))

    report = run_evaluation(world.llm, loaded, world.clock, models="jev-1.14")

    assert report.reviews == 8
    assert report.sentiment_accuracy == 1.0
    assert report.topics["staff"]["recall"] == 1.0
    assert report.topics["unclassified"]["precision"] == 1.0
    assert report.taxonomy_version == 1
    assert report.taken_at == world.clock.now()


def test_the_model_sees_the_texts_only_inside_the_data_delimiters() -> None:
    from tests.classification.helpers import requests

    loaded = sample()
    world: Setup = setup(perfect(loaded))

    run_evaluation(world.llm, loaded, world.clock, models="jev-1.14")

    sent = requests(world.openrouter)
    assert len(sent) == 8
    assert all(r.prompt.startswith("<review>\n") and r.prompt.endswith("\n</review>") for r in sent)
    assert "Obsluha byla milá" in sent[0].prompt


def test_a_model_that_fails_gives_unclassified_not_a_crash() -> None:
    loaded = sample()
    world: Setup = setup(["not json", "not json"] * 8)

    report = run_evaluation(world.llm, loaded, world.clock, models="jev-1.14")

    assert report.unclassified_share == 1.0
    assert report.topics["staff"]["recall"] == 0.0


def test_main_prints_the_table_and_saves_only_on_request(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    loaded = sample()
    last = tmp_path / "last.json"
    args = [
        "--data", str(DATA / "sample.jsonl"),
        "--taxonomy", str(DATA / "sample-taxonomy.json"),
        "--last", str(last),
    ]  # fmt: skip

    world = setup(perfect(loaded))
    assert main(args, llm=lambda: (world.llm, world.clock, "jev-1.14")) == 0
    first = capsys.readouterr().out
    assert "overall sentiment accuracy 100%" in first and "no earlier report" in first
    assert not last.exists()

    world = setup(perfect(loaded))
    assert main([*args, "--save"], llm=lambda: (world.llm, world.clock, "jev-1.14")) == 0
    assert Report.from_json(last.read_text()).reviews == 8

    world = setup([judgement({"food": "negative"})] * 8)
    assert main(args, llm=lambda: (world.llm, world.clock, "jev-1.14")) == 0
    third = capsys.readouterr().out
    assert "DROP" in third and "compared with the report of" in third


def test_main_stops_with_a_message_on_a_bad_set(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    bad = tmp_path / "set.jsonl"
    bad.write_text(json.dumps({"id": "x", "text": "a", "expected": []}) + "\n")

    code = main(
        ["--data", str(bad), "--taxonomy", str(DATA / "sample-taxonomy.json")],
        llm=lambda: pytest.fail("a bad set must stop before any model is built"),
    )

    assert code == 2 and "line 1" in capsys.readouterr().err


def test_main_says_what_is_missing_when_there_is_no_real_set(capsys: pytest.CaptureFixture[str]) -> None:
    code = main(
        ["--data", "evaluation/data/missing.jsonl"],
        llm=lambda: pytest.fail("no set, no model"),
    )

    assert code == 2 and "hand-labelled" in capsys.readouterr().err
