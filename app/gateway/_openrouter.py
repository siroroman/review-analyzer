import json
from collections.abc import Mapping
from typing import Any

from pydantic import SecretStr

from app.budget import Tokens
from app.gateway._provider import ModelRequest, count, model_request, send, tokens_in
from app.gateway._types import ClientError, ClientResponse, Usage
from app.transport import HttpRequest, HttpTransport

SERVICE = "openrouter"
_URL = "https://openrouter.ai/api/alpha/decisions"
_OUTPUT_PER_QUESTION = 50  # Jev answers are short and its output is free; this only sizes the estimate.


def _questions(schema: Mapping[str, object]) -> dict[str, dict[str, Any]]:
    """One Decisions question per field of the schema: an enum is a `choice`, a boolean a `noul`."""
    properties = schema.get("properties")
    if not isinstance(properties, dict) or not properties:
        raise ClientError("unsupported_schema")
    questions: dict[str, dict[str, Any]] = {}
    for name, spec in properties.items():
        if not isinstance(spec, dict):
            raise ClientError("unsupported_schema")
        options = spec.get("enum")
        if isinstance(options, list) and options and all(isinstance(o, str) for o in options):
            questions[name] = {"type": "choice", "criteria": {o: o for o in options}}
        elif spec.get("type") == "boolean":
            questions[name] = {"type": "noul"}
        else:
            raise ClientError("unsupported_schema")
    return questions


class OpenRouterClient:
    """ServiceClient `openrouter`: Jev through the OpenRouter Decisions API (alpha, not OpenAI compatible).

    Operation `complete`. The schema of the request is asked as typed questions; the typed answers are
    returned as the JSON text `llm` validates. `models` maps the model name of the price table to the
    model ID of the API. The key is a `SecretStr` and never leaves this class.
    """

    def __init__(
        self,
        api_key: SecretStr,
        transport: HttpTransport,
        models: Mapping[str, str],
        *,
        noul_threshold: float = 0.5,
        timeout: float = 60,
    ) -> None:
        self._key = api_key
        self._transport = transport
        self._models = dict(models)
        self._threshold = noul_threshold
        self._timeout = timeout

    def estimate(self, operation: str, request: object) -> Usage:
        asked = model_request(operation, request)
        questions = _questions(asked.json_schema)
        return Tokens(
            SERVICE,
            asked.model,
            tokens_in(asked.prompt, str(questions)),
            _OUTPUT_PER_QUESTION * len(questions),
        )

    def call(self, operation: str, request: object) -> ClientResponse:
        asked = model_request(operation, request)
        questions = _questions(asked.json_schema)
        api_model = self._models.get(asked.model)
        if api_model is None:
            raise ClientError("unknown_model")
        body = {"model": api_model, "state": asked.prompt, "questions": questions}
        exchange = send(self._transport, self._http(body))
        usage = self._usage(exchange.body, asked)
        return ClientResponse(self._payload(exchange.body, questions, usage), usage)

    def _http(self, body: Mapping[str, object]) -> HttpRequest:
        return HttpRequest(
            "POST",
            _URL,
            {"Authorization": f"Bearer {self._key.get_secret_value()}", "Content-Type": "application/json"},
            json.dumps(body, ensure_ascii=False).encode(),
            self._timeout,
        )

    @staticmethod
    def _usage(body: Mapping[str, object], asked: ModelRequest) -> Tokens:
        usage = body.get("usage")
        if not isinstance(usage, dict):
            raise ClientError("bad_response")
        return Tokens(
            SERVICE, asked.model, count(usage.get("input_tokens")), count(usage.get("output_tokens"))
        )

    def _payload(
        self, body: Mapping[str, object], questions: Mapping[str, Mapping[str, Any]], usage: Tokens
    ) -> str:
        answers = body.get("answers")
        if not isinstance(answers, dict):
            raise ClientError("bad_response", usage)
        result: dict[str, object] = {}
        for name, question in questions.items():
            answer = answers.get(name)
            if not isinstance(answer, dict):
                raise ClientError("bad_response", usage)
            if answer.get("type") == "refusal":
                raise ClientError("refusal", usage)
            if question["type"] == "choice":
                value = answer.get("choice")
                if not isinstance(value, str):
                    raise ClientError("bad_response", usage)
                result[name] = value
            else:
                score = answer.get("noul")
                if isinstance(score, bool) or not isinstance(score, int | float):
                    raise ClientError("bad_response", usage)
                result[name] = score >= self._threshold
        return json.dumps(result, ensure_ascii=False)
