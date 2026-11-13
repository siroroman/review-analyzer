class FakeInjectionDetector:
    """An InjectionDetector with scripted behaviour that remembers the texts it was asked about."""

    def __init__(self, *, flag_containing: str | None = None, fail: bool = False) -> None:
        self._flag_containing = flag_containing
        self._fail = fail
        self.seen: list[str] = []

    def is_injection(self, text: str) -> bool:
        self.seen.append(text)
        if self._fail:
            raise RuntimeError("detector unavailable")
        return self._flag_containing is not None and self._flag_containing in text.casefold()
