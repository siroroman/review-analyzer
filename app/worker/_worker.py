import logging
from enum import StrEnum
from typing import Protocol

from fastapi import FastAPI
from pydantic import BaseModel

from app.pipeline import RunResult
from app.storage import UnknownRun

_log = logging.getLogger(__name__)


class Runner(Protocol):
    """The one part of `pipeline` the worker uses."""

    def run(self, run_id: str) -> RunResult:
        """Raises `UnknownRun`."""
        ...


class Outcome(StrEnum):
    HANDLED = "handled"  # the Run is in a final status; a repeat of the message changes nothing
    UNKNOWN_RUN = "unknown_run"  # no such Run; a retry could never succeed


class Worker:
    """Takes one message (a Run id) from the queue and has `pipeline` run it. It makes no call itself.

    Delivery is at least once, and `pipeline.run` is safe to repeat: a finished Run returns its stored
    result and a half-done one resumes. Any error that is not an unknown Run propagates, so the queue
    redelivers the message.
    """

    def __init__(self, pipeline: Runner) -> None:
        self._pipeline = pipeline

    def handle(self, run_id: str) -> Outcome:
        try:
            self._pipeline.run(run_id)
        except UnknownRun:
            _log.warning("dropping a message for an unknown Run: %s", run_id)
            return Outcome.UNKNOWN_RUN
        return Outcome.HANDLED


class _Message(BaseModel):
    run_id: str


def create_worker_app(worker: Worker) -> FastAPI:
    """The push target of the queue: `POST /tasks/run` with `{"run_id": ...}`.

    2xx tells the queue the message is done (also for an unknown Run); an error is a 500, the queue retries.
    """
    app = FastAPI(title="Review Analyzer worker")

    @app.post("/tasks/run")
    def run(message: _Message) -> dict[str, str]:
        return {"outcome": worker.handle(message.run_id).value}

    return app
