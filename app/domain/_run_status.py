from enum import StrEnum


class RunStatus(StrEnum):
    """Where a Run is. A Run only moves forward; `done`, `partial` and `failed` are final."""

    QUEUED = "queued"
    DOWNLOADING = "downloading"
    CLASSIFYING = "classifying"
    ANALYZING = "analyzing"
    DONE = "done"
    PARTIAL = "partial"
    FAILED = "failed"


class InvalidTransition(ValueError):
    """A Run tried to move to a status it may not reach from where it is."""


_STEPS = (RunStatus.QUEUED, RunStatus.DOWNLOADING, RunStatus.CLASSIFYING, RunStatus.ANALYZING)
_ENDS = (RunStatus.DONE, RunStatus.PARTIAL, RunStatus.FAILED)


def advance(current: RunStatus, target: RunStatus) -> RunStatus:
    """Return `target` when a Run may move there from `current`, otherwise raise InvalidTransition."""
    if current in _ENDS:
        raise InvalidTransition(f"a {current.value} Run is finished and cannot become {target.value}")
    if target in _ENDS:
        return target
    if _STEPS.index(target) <= _STEPS.index(current):
        raise InvalidTransition(f"a Run cannot go from {current.value} to {target.value}")
    return target
