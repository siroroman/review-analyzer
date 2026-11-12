import pytest

from app.domain import InvalidTransition, RunStatus, advance

FORWARD = [
    (RunStatus.QUEUED, RunStatus.DOWNLOADING),
    (RunStatus.DOWNLOADING, RunStatus.CLASSIFYING),
    (RunStatus.CLASSIFYING, RunStatus.ANALYZING),
    (RunStatus.ANALYZING, RunStatus.DONE),
]


@pytest.mark.parametrize(("current", "target"), FORWARD)
def test_a_run_moves_one_step_forward(current: RunStatus, target: RunStatus) -> None:
    assert advance(current, target) is target


@pytest.mark.parametrize("current", [RunStatus.QUEUED, RunStatus.DOWNLOADING, RunStatus.CLASSIFYING])
def test_a_run_may_skip_ahead_to_a_later_step(current: RunStatus) -> None:
    assert advance(current, RunStatus.DONE) is RunStatus.DONE


@pytest.mark.parametrize("target", [RunStatus.PARTIAL, RunStatus.FAILED])
@pytest.mark.parametrize(
    "current",
    [RunStatus.QUEUED, RunStatus.DOWNLOADING, RunStatus.CLASSIFYING, RunStatus.ANALYZING],
)
def test_an_unfinished_run_can_end_partial_or_failed(current: RunStatus, target: RunStatus) -> None:
    assert advance(current, target) is target


@pytest.mark.parametrize(("current", "target"), [(b, a) for a, b in FORWARD])
def test_a_run_never_moves_backwards(current: RunStatus, target: RunStatus) -> None:
    with pytest.raises(InvalidTransition):
        advance(current, target)


@pytest.mark.parametrize("status", list(RunStatus))
def test_a_run_never_stays_in_the_same_status(status: RunStatus) -> None:
    with pytest.raises(InvalidTransition):
        advance(status, status)


@pytest.mark.parametrize("final", [RunStatus.DONE, RunStatus.PARTIAL, RunStatus.FAILED])
@pytest.mark.parametrize("target", list(RunStatus))
def test_a_finished_run_cannot_move_anywhere(final: RunStatus, target: RunStatus) -> None:
    with pytest.raises(InvalidTransition):
        advance(final, target)


def test_run_status_serializes_as_plain_text() -> None:
    assert RunStatus.CLASSIFYING.value == "classifying"
    assert RunStatus("partial") is RunStatus.PARTIAL
