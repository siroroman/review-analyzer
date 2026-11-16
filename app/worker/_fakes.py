from app.worker._auth import CallerClaims, InvalidToken


class FakeTokenVerifier:
    """A `TokenVerifier` that knows only the tokens it issued."""

    def __init__(self) -> None:
        self._tokens: dict[str, tuple[str, CallerClaims, bool]] = {}

    def issue(self, *, email: str, audience: str, email_verified: bool = True, expired: bool = False) -> str:
        token = f"token-{len(self._tokens)}"
        self._tokens[token] = (audience, CallerClaims(email, email_verified), expired)
        return token

    def verify(self, token: str, audience: str) -> CallerClaims:
        issued = self._tokens.get(token)
        if issued is None:
            raise InvalidToken("unknown token")
        issued_for, claims, expired = issued
        if expired:
            raise InvalidToken("expired")
        if issued_for != audience:
            raise InvalidToken("wrong audience")
        return claims
