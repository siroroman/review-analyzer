import logging
import queue
import threading
from collections.abc import Callable
from datetime import timedelta

from app.queue._types import QueueError

_log = logging.getLogger(__name__)
_DEFAULT_ATTEMPTS = 5
_DEFAULT_DELAY = timedelta(seconds=5)


class LocalQueue:
    """The `Queue` of a laptop: a background thread hands each message to `handler` (the worker).

    Like the real queue it delivers at least once: a handler that raises gets the message again after
    `retry_delay`, up to `max_attempts` times. A message that is already waiting is not added twice; a
    repeat after it was handled reaches the worker, which makes it cost nothing. Messages wait in memory
    only, so they are lost when the process stops: this is for local runs, not for a deployment.
    """

    def __init__(
        self,
        handler: Callable[[str], object],
        sleep: Callable[[timedelta], None],
        *,
        max_attempts: int = _DEFAULT_ATTEMPTS,
        retry_delay: timedelta = _DEFAULT_DELAY,
    ) -> None:
        self._handler = handler
        self._sleep = sleep
        self._max_attempts = max_attempts
        self._retry_delay = retry_delay
        self._messages: queue.Queue[str] = queue.Queue()
        self._waiting: set[str] = set()
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None

    def enqueue(self, run_id: str) -> None:
        if not run_id.strip():
            raise QueueError("the Run id cannot be empty")
        with self._lock:
            if run_id in self._waiting:
                return
            self._waiting.add(run_id)
            self._messages.put(run_id)
            if self._thread is None:
                self._thread = threading.Thread(target=self._work, name="local-queue", daemon=True)
                self._thread.start()

    def join(self) -> None:
        """Block until every message so far is handled or given up. For tests and a clean shutdown."""
        self._messages.join()

    def _work(self) -> None:
        while True:
            run_id = self._messages.get()
            try:
                self._deliver(run_id)
            finally:
                with self._lock:
                    self._waiting.discard(run_id)
                self._messages.task_done()

    def _deliver(self, run_id: str) -> None:
        for attempt in range(1, self._max_attempts + 1):
            try:
                self._handler(run_id)
            except Exception:
                _log.exception("Run %s failed, attempt %d of %d", run_id, attempt, self._max_attempts)
                if attempt < self._max_attempts:
                    self._sleep(self._retry_delay)
            else:
                return
