import datetime as dt
import json
import time
from typing import Any

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID
from google.auth import crypt, jwt
from google.auth.transport import Request, Response

from app.worker import GoogleTokenVerifier, InvalidToken

AUDIENCE = "https://worker.example.run.app"
ACCOUNT = "queue@project.iam.gserviceaccount.com"
KID = "test-key"


def make_key() -> tuple[rsa.RSAPrivateKey, str]:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "test")])
    now = dt.datetime.now(dt.UTC)
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(1)
        .not_valid_before(now - dt.timedelta(days=1))
        .not_valid_after(now + dt.timedelta(days=1))
        .sign(key, hashes.SHA256())
    )
    return key, cert.public_bytes(serialization.Encoding.PEM).decode()


class FakeResponse(Response):
    def __init__(self, data: bytes) -> None:
        self._data = data

    @property
    def status(self) -> int:
        return 200

    @property
    def headers(self) -> dict[str, str]:
        return {}

    @property
    def data(self) -> bytes:
        return self._data


class FakeCertsRequest(Request):
    """Answers the fetch of Google's public certificates from a fixture instead of the network."""

    def __init__(self, certs: dict[str, str]) -> None:
        self._body = json.dumps(certs).encode()

    def __call__(  # type: ignore[override]
        self, url: str, method: str = "GET", **kwargs: Any
    ) -> FakeResponse:
        return FakeResponse(self._body)


def token(key: rsa.RSAPrivateKey, **overrides: Any) -> str:
    pem = key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
    ).decode()
    now = int(time.time())
    claims = {
        "iss": "https://accounts.google.com",
        "aud": AUDIENCE,
        "email": ACCOUNT,
        "email_verified": True,
        "iat": now,
        "exp": now + 600,
    } | overrides
    signer = crypt.RSASigner.from_string(pem, KID)  # type: ignore[no-untyped-call]
    encoded: bytes = jwt.encode(signer, claims, {"kid": KID})  # type: ignore[no-untyped-call]
    return encoded.decode()


def test_a_token_signed_with_a_google_key_for_the_audience_gives_the_caller() -> None:
    key, cert = make_key()
    verifier = GoogleTokenVerifier(FakeCertsRequest({KID: cert}))

    claims = verifier.verify(token(key), AUDIENCE)

    assert claims.email == ACCOUNT
    assert claims.email_verified is True


def test_a_token_for_another_audience_is_invalid() -> None:
    key, cert = make_key()
    verifier = GoogleTokenVerifier(FakeCertsRequest({KID: cert}))

    with pytest.raises(InvalidToken):
        verifier.verify(token(key, aud="https://other.example"), AUDIENCE)


def test_an_expired_token_is_invalid() -> None:
    key, cert = make_key()
    verifier = GoogleTokenVerifier(FakeCertsRequest({KID: cert}))
    long_ago = int(time.time()) - 7200

    with pytest.raises(InvalidToken):
        verifier.verify(token(key, iat=long_ago, exp=long_ago + 600), AUDIENCE)


def test_a_token_signed_with_an_unknown_key_is_invalid() -> None:
    key, _ = make_key()
    _, other_cert = make_key()
    verifier = GoogleTokenVerifier(FakeCertsRequest({KID: other_cert}))

    with pytest.raises(InvalidToken):
        verifier.verify(token(key), AUDIENCE)


def test_garbage_is_invalid() -> None:
    _, cert = make_key()

    with pytest.raises(InvalidToken):
        GoogleTokenVerifier(FakeCertsRequest({KID: cert})).verify("not.a.jwt", AUDIENCE)
