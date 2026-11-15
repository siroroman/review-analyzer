"""Pipeline: one Run from a queued Run to a result, a Partial result or a failure (ADR-0004, ADR-0005)."""

from app.pipeline._pipeline import Pipeline
from app.pipeline._types import PipelineConfig, RunResult

__all__ = ["Pipeline", "PipelineConfig", "RunResult"]
