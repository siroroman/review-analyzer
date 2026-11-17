"""Pipeline: one Run from a queued Run to a result, a Partial result or a failure (ADR-0004, ADR-0005)."""

from app.pipeline._pipeline import Pipeline, PlaceDetailsFetcher
from app.pipeline._types import NOTE_INDUSTRY_FALLBACK, PipelineConfig, RunReport, RunResult

__all__ = [
    "NOTE_INDUSTRY_FALLBACK",
    "Pipeline",
    "PipelineConfig",
    "PlaceDetailsFetcher",
    "RunReport",
    "RunResult",
]
