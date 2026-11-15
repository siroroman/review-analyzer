"""Evaluation of classification on a hand-labelled set. Manual or nightly, never in CI."""

from evaluation._data import EvaluationSet, Expected, InvalidSet, SetItem, load_set
from evaluation._report import DROP_THRESHOLD, Report, build_report, render
from evaluation._score import Scores, TopicScore, score

__all__ = [
    "DROP_THRESHOLD",
    "EvaluationSet",
    "Expected",
    "InvalidSet",
    "Report",
    "Scores",
    "SetItem",
    "TopicScore",
    "build_report",
    "load_set",
    "render",
    "score",
]
