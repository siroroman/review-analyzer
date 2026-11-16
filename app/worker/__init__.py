"""Worker: takes a queued Run's message and has `pipeline` run it. Thin: no business logic, no paid call."""

from app.worker._auth import CallerClaims, InvalidToken, NoAuthCheck, OidcCheck, TokenVerifier
from app.worker._config import WorkerAuthConfigError, auth_from_env
from app.worker._fakes import FakeTokenVerifier
from app.worker._worker import Outcome, Runner, Worker, create_worker_app

__all__ = [
    "CallerClaims",
    "FakeTokenVerifier",
    "InvalidToken",
    "NoAuthCheck",
    "OidcCheck",
    "Outcome",
    "Runner",
    "TokenVerifier",
    "Worker",
    "WorkerAuthConfigError",
    "auth_from_env",
    "create_worker_app",
]
