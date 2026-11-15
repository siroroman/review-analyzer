"""Evaluation of classification on a hand-labelled set. Manual or nightly, never in CI."""

from evaluation._data import EvaluationSet, Expected, InvalidSet, SetItem, load_set

__all__ = ["EvaluationSet", "Expected", "InvalidSet", "SetItem", "load_set"]
