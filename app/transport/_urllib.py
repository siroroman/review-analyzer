import urllib.error
import urllib.request
from urllib.parse import urlsplit

from app.transport._types import HttpError, HttpRequest, HttpResponse, HttpTimeout


class UrllibTransport:
    """HttpTransport on the standard library. Follows no redirect to another scheme, sends only http(s)."""

    def send(self, request: HttpRequest) -> HttpResponse:
        if urlsplit(request.url).scheme not in ("http", "https"):
            raise HttpError("only http and https are allowed")
        call = urllib.request.Request(  # noqa: S310 - scheme checked above
            request.url, data=request.body, headers=dict(request.headers), method=request.method
        )
        try:
            with urllib.request.urlopen(call, timeout=request.timeout) as answer:  # noqa: S310
                return HttpResponse(answer.status, answer.read())
        except urllib.error.HTTPError as failure:
            return HttpResponse(failure.code, failure.read())
        except TimeoutError:
            raise HttpTimeout("timeout") from None
        except urllib.error.URLError as failure:
            if isinstance(failure.reason, TimeoutError):
                raise HttpTimeout("timeout") from None
            raise HttpError("connection failed") from None
        except OSError:
            raise HttpError("connection failed") from None
