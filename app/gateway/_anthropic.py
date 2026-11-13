import json
from collections.abc import Mapping

from pydantic import SecretStr

from app.budget import Tokens
from app.gateway._provider import count, model_request, send, tokens_in
from app.gateway._types import ClientError, ClientResponse, Usage
from app.transport import HttpRequest, HttpTransport

SERVICE = "anthropic"
_URL = "https://api.anthropic.com/v1/messages"
_VERSION = "2023-06-01"
_SCHEMA_RULE = (
    "Answer with only one JSON object that is valid for this JSON Schema, with no other text:\n{schema}"
)


class AnthropicClient:
    """ServiceClient `anthropic`: Claude through the Messages API. Operation `complete`.

    `models` maps the model name of the price table (`claude-haiku`) to the model ID of the API. The
    schema goes into the system block, which carries the prompt-caching mark when `cache_system` is set.
    Tokens written to or read from the cache are billed as plain input: an upper bound, never an
    under-count. The key is a `SecretStr` and never leaves this class.
    """

    def __init__(
        self,
        api_key: SecretStr,
        transport: HttpTransport,
        models: Mapping[str, str],
        *,
        max_output_tokens: int = 4096,
        timeout: float = 120,
    ) -> None:
        if max_output_tokens < 1:
            raise ValueError("max_output_tokens must be positive")
        self._key = api_key
        self._transport = transport
        self._models = dict(models)
        self._max_output = max_output_tokens
        self._timeout = timeout

    def estimate(self, operation: str, request: object) -> Usage:
        asked = model_request(operation, request)
        system = self._system(asked.system, asked.json_schema)
        return Tokens(SERVICE, asked.model, tokens_in(asked.prompt, system), self._max_output)

    def call(self, operation: str, request: object) -> ClientResponse:
        asked = model_request(operation, request)
        api_model = self._models.get(asked.model)
        if api_model is None:
            raise ClientError("unknown_model")
        block: dict[str, object] = {"type": "text", "text": self._system(asked.system, asked.json_schema)}
        if asked.cache_system:
            block["cache_control"] = {"type": "ephemeral"}
        body = {
            "model": api_model,
            "max_tokens": self._max_output,
            "system": [block],
            "messages": [{"role": "user", "content": asked.prompt}],
        }
        exchange = send(self._transport, self._http(body)).body
        usage = self._usage(exchange, asked.model)
        if exchange.get("stop_reason") == "max_tokens":
            raise ClientError("truncated", usage)
        return ClientResponse(self._text(exchange, usage), usage)

    @staticmethod
    def _system(system: str | None, schema: Mapping[str, object]) -> str:
        rule = _SCHEMA_RULE.format(schema=json.dumps(schema, ensure_ascii=False))
        return rule if system is None else f"{system}\n\n{rule}"

    def _http(self, body: Mapping[str, object]) -> HttpRequest:
        return HttpRequest(
            "POST",
            _URL,
            {
                "x-api-key": self._key.get_secret_value(),
                "anthropic-version": _VERSION,
                "content-type": "application/json",
            },
            json.dumps(body, ensure_ascii=False).encode(),
            self._timeout,
        )

    @staticmethod
    def _usage(body: Mapping[str, object], model: str) -> Tokens:
        usage = body.get("usage")
        if not isinstance(usage, dict):
            raise ClientError("bad_response")
        plain = count(usage.get("input_tokens"))
        written = count(usage.get("cache_creation_input_tokens", 0))
        read = count(usage.get("cache_read_input_tokens", 0))
        return Tokens(SERVICE, model, plain + written + read, count(usage.get("output_tokens")))

    @staticmethod
    def _text(body: Mapping[str, object], usage: Tokens) -> str:
        content = body.get("content")
        if not isinstance(content, list):
            raise ClientError("bad_response", usage)
        parts = [b["text"] for b in content if isinstance(b, dict) and isinstance(b.get("text"), str)]
        if not parts:
            raise ClientError("bad_response", usage)
        return "".join(parts)
