import uuid


class UuidIds:
    """IdSource on random UUIDs: the one place where an adapter draws randomness, behind its port."""

    def new_id(self) -> str:
        return str(uuid.uuid4())


class FakeIds:
    """An IdSource that counts: `id-1`, `id-2`, ..."""

    def __init__(self) -> None:
        self._next = 0

    def new_id(self) -> str:
        self._next += 1
        return f"id-{self._next}"
