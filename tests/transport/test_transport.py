import threading
import time
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from app.transport import (
    FakeTransport,
    HttpError,
    HttpRequest,
    HttpResponse,
    HttpTimeout,
    MissingSecret,
    UrllibTransport,
    read_secret,
)


class _Handler(BaseHTTPRequestHandler):
    def do_POST(self) -> None:  # noqa: N802
        size = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(size)
        if self.path == "/slow":
            time.sleep(0.5)
        status = 429 if self.path == "/limited" else 200
        reply = b"echo:" + body + b"|" + self.headers.get("X-Test", "").encode()
        self.send_response(status)
        self.send_header("Content-Length", str(len(reply)))
        self.end_headers()
        self.wfile.write(reply)

    def log_message(self, format: str, *args: object) -> None:  # noqa: A002
        return


@pytest.fixture
def server() -> Iterator[str]:
    httpd = HTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{httpd.server_port}"
    httpd.shutdown()
    httpd.server_close()


def post(url: str, timeout: float = 5) -> HttpRequest:
    return HttpRequest("POST", url, {"X-Test": "yes"}, b"hello", timeout)


def test_returns_status_and_body(server: str) -> None:
    answer = UrllibTransport().send(post(server + "/ok"))
    assert answer == HttpResponse(200, b"echo:hello|yes")


def test_an_error_status_is_an_answer_not_an_exception(server: str) -> None:
    answer = UrllibTransport().send(post(server + "/limited"))
    assert answer.status == 429


def test_a_slow_server_times_out(server: str) -> None:
    with pytest.raises(HttpTimeout):
        UrllibTransport().send(post(server + "/slow", timeout=0.05))


def test_no_listener_is_an_http_error_without_the_url() -> None:
    with pytest.raises(HttpError) as failure:
        UrllibTransport().send(post("http://127.0.0.1:1/secret-path", timeout=1))
    assert "secret-path" not in str(failure.value)
    assert not isinstance(failure.value, HttpTimeout)


def test_only_http_and_https_are_sent() -> None:
    with pytest.raises(HttpError):
        UrllibTransport().send(post("file:///etc/passwd"))


def test_fake_transport_plays_its_script_and_remembers_requests() -> None:
    fake = FakeTransport(HttpResponse(200, b"a"), HttpTimeout("timeout"))
    request = post("https://example.test/x")
    assert fake.send(request).body == b"a"
    with pytest.raises(HttpTimeout):
        fake.send(request)
    assert fake.requests == [request, request]


def test_a_secret_is_read_from_configuration_and_hidden() -> None:
    secret = read_secret({"KEY": " abc123 "}, "KEY")
    assert secret.get_secret_value() == "abc123"
    assert "abc123" not in repr(secret) and "abc123" not in str(secret)


@pytest.mark.parametrize("environ", [{}, {"KEY": ""}, {"KEY": "  "}])
def test_a_missing_secret_names_the_setting(environ: dict[str, str]) -> None:
    with pytest.raises(MissingSecret, match="KEY"):
        read_secret(environ, "KEY")


def test_a_request_never_shows_headers_or_body_in_its_repr() -> None:
    request = HttpRequest("POST", "https://x.test", {"Authorization": "Bearer sk-1"}, b"body-text", 1)
    assert "sk-1" not in repr(request) and "body-text" not in repr(request)


def test_a_refused_connection_to_a_closed_port_is_not_a_timeout() -> None:
    import socket

    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    with pytest.raises(HttpError) as failure:
        UrllibTransport().send(post(f"http://127.0.0.1:{port}/x", timeout=1))
    assert not isinstance(failure.value, HttpTimeout)
