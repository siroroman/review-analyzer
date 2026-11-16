from dataclasses import dataclass
from typing import Protocol


class InvalidToken(Exception):
    """The token's signature, audience or expiry is wrong."""


@dataclass(frozen=True)
class CallerClaims:
    email: str
    email_verified: bool


class TokenVerifier(Protocol):
    """Checks an OIDC token: signature, audience and expiry. Account checks are the worker's."""

    def verify(self, token: str, audience: str) -> CallerClaims:
        """Raises `InvalidToken`."""
        ...


@dataclass(frozen=True)
class OidcCheck:
    """Only a call from `service_account_email` with a token made for `audience` gets through."""

    verifier: TokenVerifier
    audience: str
    service_account_email: str

    def allows(self, authorization: str | None) -> bool:
        scheme, _, token = (authorization or "").partition(" ")
        if scheme.lower() != "bearer" or not token:
            return False
        try:
            claims = self.verifier.verify(token, self.audience)
        except InvalidToken:
            return False
        return claims.email_verified and claims.email == self.service_account_email


@dataclass(frozen=True)
class NoAuthCheck:
    """Lets every call through. Only for the local run with the in-process queue; never a default."""

    def allows(self, authorization: str | None) -> bool:
        return True
