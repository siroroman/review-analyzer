"""Insights: prompts, the strong model, Grounding and the content check (ADR-0004)."""

from app.insights._fakes import CompleterCall, FakeCompleter
from app.insights._generate import InsightGenerator
from app.insights._prompt import MAX_SAMPLE_CHARS, MAX_SAMPLES
from app.insights._types import Completer, Insights

__all__ = [
    "MAX_SAMPLES",
    "MAX_SAMPLE_CHARS",
    "Completer",
    "CompleterCall",
    "FakeCompleter",
    "InsightGenerator",
    "Insights",
]
