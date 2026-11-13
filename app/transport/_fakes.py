from app.transport._types import HttpError, HttpRequest, HttpResponse


class FakeTransport:
    """An HttpTransport that plays scripted answers in order and remembers every request."""

    def __init__(self, *steps: HttpResponse | HttpError) -> None:
        self._steps = list(steps)
        self.requests: list[HttpRequest] = []

    def send(self, request: HttpRequest) -> HttpResponse:
        self.requests.append(request)
        step = self._steps.pop(0)
        if isinstance(step, HttpError):
            raise step
        return step
