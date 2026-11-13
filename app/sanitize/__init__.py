"""Sanitize: untrusted Raw Reviews become safe, anonymous, deduplicated Reviews. Pure, no I/O (ADR-0004)."""

from app.sanitize._detectors import PatternInjectionDetector
from app.sanitize._fakes import FakeInjectionDetector
from app.sanitize._prepare import prepare
from app.sanitize._text import MAX_TEXT_LENGTH
from app.sanitize._types import InjectionDetector, PreparedReviews

__all__ = [
    "MAX_TEXT_LENGTH",
    "FakeInjectionDetector",
    "InjectionDetector",
    "PatternInjectionDetector",
    "PreparedReviews",
    "prepare",
]
