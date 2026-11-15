from collections.abc import Callable


class FakeQueue:
    """An in-process `Queue`. `enqueued` is every message ever accepted, in order; `pending` is what a
    delivery has not yet handled."""

    def __init__(self) -> None:
        self.enqueued: list[str] = []
        self.pending: list[str] = []

    def enqueue(self, run_id: str) -> None:
        self.enqueued.append(run_id)
        self.pending.append(run_id)

    def deliver(self, handler: Callable[[str], object]) -> int:
        """Hand each pending message to `handler`, oldest first; return how many were handled.

        A message whose handler raises stays pending, like a message the real queue redelivers: the
        error reaches the caller.
        """
        handled = 0
        while self.pending:
            handler(self.pending[0])
            self.pending.pop(0)
            handled += 1
        return handled
