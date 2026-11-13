"""LLM: one entry point to a model. Routing, retry, fallback, validation, tracing (ADR-0003, ADR-0006)."""

from app.llm._fakes import FakeSleeper, FakeTracer
from app.llm._llm import Llm
from app.llm._types import (
    CompletionGateway,
    CompletionRequest,
    InvalidOutput,
    LlmConfig,
    LlmError,
    ModelRef,
    Route,
    Sleeper,
    TraceEvent,
    Tracer,
    UnknownTask,
)

__all__ = [
    "CompletionGateway",
    "CompletionRequest",
    "FakeSleeper",
    "FakeTracer",
    "InvalidOutput",
    "Llm",
    "LlmConfig",
    "LlmError",
    "ModelRef",
    "Route",
    "Sleeper",
    "TraceEvent",
    "Tracer",
    "UnknownTask",
]
