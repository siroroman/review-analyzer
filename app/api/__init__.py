"""API: the HTTP layer of the dashboard. It parses a request, calls a module, serializes the answer."""

from app.api._app import create_app
from app.api._types import ApiConfig, FakeQueue, Queue

__all__ = ["ApiConfig", "FakeQueue", "Queue", "create_app"]
