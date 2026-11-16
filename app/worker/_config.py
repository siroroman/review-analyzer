from collections.abc import Mapping

from app.worker._auth import NoAuthCheck, OidcCheck, TokenVerifier


class WorkerAuthConfigError(Exception):
    """The worker's auth settings are incomplete. The worker does not start rather than skip the check."""


def auth_from_env(env: Mapping[str, str], verifier: TokenVerifier) -> OidcCheck | NoAuthCheck:
    """`WORKER_OIDC_AUDIENCE` and `WORKER_OIDC_SERVICE_ACCOUNT` turn the check on.

    The check is off only when `WORKER_AUTH_DISABLED` is exactly `true` (the local run with the in-process
    queue). Anything else that is missing raises `WorkerAuthConfigError`.
    """
    if env.get("WORKER_AUTH_DISABLED") == "true":
        return NoAuthCheck()
    audience = env.get("WORKER_OIDC_AUDIENCE", "")
    account = env.get("WORKER_OIDC_SERVICE_ACCOUNT", "")
    if not audience or not account:
        raise WorkerAuthConfigError(
            "set WORKER_OIDC_AUDIENCE and WORKER_OIDC_SERVICE_ACCOUNT, "
            "or WORKER_AUTH_DISABLED=true for a local run"
        )
    return OidcCheck(verifier=verifier, audience=audience, service_account_email=account)
