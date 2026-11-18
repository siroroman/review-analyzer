import json
from collections.abc import Mapping

from pydantic import SecretStr

from app.budget import Tokens
from app.gateway._provider import count, model_request, send, tokens_in
from app.gateway._types import ClientError, ClientResponse, Usage
from app.transport import HttpRequest, HttpTransport

SERVICE = "openrouter_chat"
_URL = "https://openrouter.ai/api/v1/chat/completions"
_SCHEMA_RULE = (
    "Answer with only one JSON object that is valid for this JSON Schema, with no other text:\n{schema}"
)


class OpenRouterChatClient:
    """ServiceClient `openrouter_chat`: DeepSeek through the OpenRouter chat completions API.

    Operation `complete`. `models` maps the model name of the price table (`deepseek-v4.1-flash`) to
    the model ID of the API. The schema goes into the system message and the answer must be a JSON
    object. The key is a `SecretStr` and never leaves this class.
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
        body = {
            "model": api_model,
            "max_tokens": self._max_output,
            "response_format": {"type": "json_object"},
            # The model reasons by default and can spend the whole output on it, leaving an empty answer.
            "reasoning": {"enabled": False},
            "messages": [
                {"role": "system", "content": self._system(asked.system, asked.json_schema)},
                {"role": "user", "content": asked.prompt},
            ],
        }
        exchange = send(self._transport, self._http(body)).body
        usage = self._usage(exchange, asked.model)
        choice = self._choice(exchange, usage)
        if choice.get("finish_reason") == "length":
            raise ClientError("truncated", usage)
        return ClientResponse(self._text(choice, usage), usage)

    @staticmethod
    def _system(system: str | None, schema: Mapping[str, object]) -> str:
        rule = _SCHEMA_RULE.format(schema=json.dumps(schema, ensure_ascii=False))
        return rule if system is None else f"{system}\n\n{rule}"

    def _http(self, body: Mapping[str, object]) -> HttpRequest:
        return HttpRequest(
            "POST",
            _URL,
            {"Authorization": f"Bearer {self._key.get_secret_value()}", "Content-Type": "application/json"},
            json.dumps(body, ensure_ascii=False).encode(),
            self._timeout,
        )

    @staticmethod
    def _usage(body: Mapping[str, object], model: str) -> Tokens:
        usage = body.get("usage")
        if not isinstance(usage, dict):
            raise ClientError("bad_response")
        return Tokens(
            SERVICE, model, count(usage.get("prompt_tokens")), count(usage.get("completion_tokens"))
        )

    @staticmethod
    def _choice(body: Mapping[str, object], usage: Tokens) -> Mapping[str, object]:
        choices = body.get("choices")
        if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
            raise ClientError("bad_response", usage)
        return choices[0]

    @staticmethod
    def _text(choice: Mapping[str, object], usage: Tokens) -> str:
        message = choice.get("message")
        text = message.get("content") if isinstance(message, dict) else None
        if not isinstance(text, str) or not text:
            raise ClientError("bad_response", usage)
        return text
