"""Evaluation of classification on a hand-labelled set. Manual or nightly, never in CI."""

from evaluation._data import EvaluationSet, Expected, InvalidSet, SetItem, load_set
from evaluation._score import Scores, TopicScore, score

__all__ = [
    "EvaluationSet",
    "Expected",
    "InvalidSet",
    "Scores",
    "SetItem",
    "TopicScore",
    "load_set",
    "score",
]
