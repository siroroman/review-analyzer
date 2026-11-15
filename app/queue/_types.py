from typing import Protocol


class Queue(Protocol):
    """Port: hands a queued Run to the worker. The message is the Run id, nothing else.

    Delivery is at least once: the worker may get the same message again.
    """

    def enqueue(self, run_id: str) -> None:
        """Raises `QueueError` when the message was not accepted."""
        ...


class QueueError(Exception):
    """The queue did not accept a message. The text never holds a URL, a token or a response body."""
