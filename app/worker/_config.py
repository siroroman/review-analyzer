from collections.abc import Mapping

from app.worker._auth import NoAuthCheck, OidcCheck, TokenVerifier


class WorkerAuthConfigError(Exception):
    """The worker's auth settings are incomplete. The worker does not start rather than skip the check."""


def auth_from_env(env: Mapping[str, str], verifier: TokenVerifier) -> OidcCheck | NoAuthCheck:
    """`WORKER_URL` (the audience Cloud Tasks puts in the token) and `WORKER_SERVICE_ACCOUNT` turn the
    check on; they are the same variables the queue sends tasks with, so the two cannot drift apart.

    The check is off only when `WORKER_AUTH_DISABLED` is exactly `true` (the local run with the in-process
    queue). Anything else that is missing raises `WorkerAuthConfigError`.
    """
    if env.get("WORKER_AUTH_DISABLED") == "true":
        return NoAuthCheck()
    audience = env.get("WORKER_URL", "")
    account = env.get("WORKER_SERVICE_ACCOUNT", "")
    if not audience or not account:
        raise WorkerAuthConfigError(
            "set WORKER_URL and WORKER_SERVICE_ACCOUNT, or WORKER_AUTH_DISABLED=true for a local run"
        )
    return OidcCheck(verifier=verifier, audience=audience, service_account_email=account)
