from google.auth import exceptions
from google.auth.transport import Request
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token

from app.worker._auth import CallerClaims, InvalidToken


class GoogleTokenVerifier:
    """Checks a Google-signed OIDC token (what Cloud Tasks sends): signature, audience and expiry.

    Google's public certificates are fetched with `request` on each call; a failed fetch is not an invalid
    token, it propagates so the queue redelivers the message.
    """

    def __init__(self, request: Request | None = None) -> None:
        self._request = request or google_requests.Request()

    def verify(self, token: str, audience: str) -> CallerClaims:
        try:
            claims = id_token.verify_oauth2_token(  # type: ignore[no-untyped-call]
                token, self._request, audience=audience
            )
        except exceptions.TransportError:
            raise
        except ValueError as error:
            raise InvalidToken(str(error)) from error
        return CallerClaims(
            email=str(claims.get("email", "")), email_verified=claims.get("email_verified") is True
        )
