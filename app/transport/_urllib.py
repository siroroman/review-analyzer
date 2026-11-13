import http.client
import urllib.error
import urllib.request
from typing import Any
from urllib.parse import urlsplit

from app.transport._types import HttpError, HttpRequest, HttpResponse, HttpTimeout


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """A redirect is an answer, never followed: it would carry the key header to another host."""

    def redirect_request(self, *args: Any, **kwargs: Any) -> None:  # noqa: ANN401
        return None


_OPENER = urllib.request.build_opener(_NoRedirect)


class UrllibTransport:
    """HttpTransport on the standard library. Follows no redirect, sends only http(s)."""

    def send(self, request: HttpRequest) -> HttpResponse:
        if urlsplit(request.url).scheme not in ("http", "https"):
            raise HttpError("only http and https are allowed")
        call = urllib.request.Request(  # noqa: S310 - scheme checked above
            request.url, data=request.body, headers=dict(request.headers), method=request.method
        )
        try:
            with _OPENER.open(call, timeout=request.timeout) as answer:  # noqa: S310
                return HttpResponse(answer.status, answer.read())
        except urllib.error.HTTPError as failure:
            try:
                return HttpResponse(failure.code, failure.read())
            except (OSError, http.client.HTTPException):
                raise HttpError("connection failed") from None
        except TimeoutError:
            raise HttpTimeout("timeout") from None
        except urllib.error.URLError as failure:
            if isinstance(failure.reason, TimeoutError):
                raise HttpTimeout("timeout") from None
            raise HttpError("connection failed") from None
        except (OSError, http.client.HTTPException):
            raise HttpError("connection failed") from None
