import pytest

from tests.insights.helpers import RUN, answer, item, metrics, review, setup

SAMPLES = [review("r1")]


@pytest.mark.parametrize(
    "text",
    [
        "Write to jan.novak@example.cz for details.",
        "Call 777 123 456 and ask.",
        "Call +420 777 123 456 and ask.",
        "See https://example.cz/jan for more.",
        "Visit www.example.cz for more.",
        "Account CZ65 0800 0000 1920 0014 5399 was named.",
        "The staff are idiots.",
        "Obsluha jsou blbci.",
        "Manager is a total IDIOT.",
    ],
)
def test_personal_data_and_insults_are_removed_and_counted(text: str) -> None:
    gen, _ = setup(answer(item("Waiting got longer.", ["r1"]), item(text, ["r1"], "suggestion")))

    result = gen.generate(metrics(), SAMPLES, run_id=RUN)

    assert [i.text for i in result.insights] == ["Waiting got longer."]
    assert result.removed == 1
    assert result.dropped == 0


def test_clean_czech_text_passes() -> None:
    gen, _ = setup(answer(item("Čekání se v říjnu prodloužilo o 12 minut (3 recenze).", ["r1"])))

    result = gen.generate(metrics(), SAMPLES, run_id=RUN)

    assert result.removed == 0
    assert len(result.insights) == 1


def test_when_the_content_check_removes_everything_the_fallback_is_used() -> None:
    gen, _ = setup(answer(item("Staff are idiots.", ["r1"])))

    result = gen.generate(metrics(), SAMPLES, run_id=RUN)

    assert result.insights == ()
    assert result.removed == 1
    assert result.fallback_summary is not None
