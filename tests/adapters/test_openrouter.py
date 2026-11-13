import json
from decimal import Decimal

import pytest
from pydantic import BaseModel, SecretStr

from app.gateway import ClientError, ClientTimeout, OpenRouterClient, Tokens
from app.llm import CompletionRequest
from app.transport import FakeTransport, HttpError, HttpResponse, HttpTimeout
from tests.adapters.helpers import Verdict, body_of, fixture

KEY = "sk-or-secret-1234"
MODELS = {"jev-1.14": "typesafe/jev-1.14"}


def client(*steps: HttpResponse | HttpError) -> tuple[OpenRouterClient, FakeTransport]:
    transport = FakeTransport(*steps)
    return OpenRouterClient(SecretStr(KEY), transport, MODELS), transport


def request(prompt: str = "Pokoj byl špinavý.", schema: type[BaseModel] = Verdict) -> CompletionRequest:
    return CompletionRequest("jev-1.14", prompt, "ignored system", False, schema.model_json_schema())


def test_answers_become_json_for_the_schema_and_usage_is_the_providers() -> None:
    adapter, _ = client(fixture("openrouter_decisions_ok.json"))
    response = adapter.call("complete", request())
    assert isinstance(response.payload, str)
    assert Verdict.model_validate_json(response.payload) == Verdict(sentiment="negative", injection=False)
    assert response.usage == Tokens("openrouter", "jev-1.14", 412, 6)


def test_sends_the_prompt_as_state_and_one_question_per_field() -> None:
    adapter, transport = client(fixture("openrouter_decisions_ok.json"))
    adapter.call("complete", request("Pokoj byl špinavý."))
    sent = transport.requests[0]
    assert sent.method == "POST"
    assert sent.url == "https://openrouter.ai/api/alpha/decisions"
    assert sent.headers["Authorization"] == f"Bearer {KEY}"
    body = body_of(sent.body)
    assert body["model"] == "typesafe/jev-1.14"
    assert body["state"] == "Pokoj byl špinavý."
    assert body["questions"] == {
        "sentiment": {
            "type": "choice",
            "criteria": {"positive": "positive", "neutral": "neutral", "negative": "negative"},
        },
        "injection": {"type": "noul"},
    }


def test_a_noul_answer_is_a_boolean_by_the_threshold() -> None:
    answers = json.loads(fixture("openrouter_decisions_ok.json").body)
    answers["answers"]["injection"]["noul"] = 0.91
    adapter, _ = client(HttpResponse(200, json.dumps(answers).encode()))
    response = adapter.call("complete", request())
    assert isinstance(response.payload, str)
    assert Verdict.model_validate_json(response.payload).injection is True


def test_a_refusal_fails_the_call_and_charges_what_was_used() -> None:
    adapter, _ = client(fixture("openrouter_decisions_refusal.json"))
    with pytest.raises(ClientError) as failure:
        adapter.call("complete", request())
    assert failure.value.kind == "refusal"
    assert failure.value.usage == Tokens("openrouter", "jev-1.14", 300, 2)


def test_a_schema_it_cannot_ask_as_questions_is_refused_before_any_call() -> None:
    class Free(BaseModel):
        reasoning: str

    adapter, transport = client()
    with pytest.raises(ClientError) as failure:
        adapter.call("complete", request(schema=Free))
    assert failure.value.kind == "unsupported_schema"
    assert transport.requests == []


@pytest.mark.parametrize(
    ("status", "kind"),
    [
        (429, "rate_limited"),
        (500, "server_error"),
        (503, "server_error"),
        (529, "server_error"),
        (401, "auth"),
        (403, "auth"),
        (402, "payment"),
        (400, "bad_request"),
        (413, "bad_request"),
        (404, "http_error"),
    ],
)
def test_an_error_status_is_a_client_error_of_a_short_kind(status: int, kind: str) -> None:
    adapter, _ = client(HttpResponse(status, b'{"error": "Bearer sk-or-secret-1234 leaked text"}'))
    with pytest.raises(ClientError) as failure:
        adapter.call("complete", request())
    assert failure.value.kind == kind
    assert failure.value.usage is None
    assert KEY not in str(failure.value) and "leaked" not in str(failure.value)


def test_a_timeout_is_a_client_timeout() -> None:
    adapter, _ = client(HttpTimeout("timeout"))
    with pytest.raises(ClientTimeout):
        adapter.call("complete", request())


def test_a_dropped_connection_is_a_connection_error() -> None:
    adapter, _ = client(HttpError("connection failed"))
    with pytest.raises(ClientError) as failure:
        adapter.call("complete", request())
    assert failure.value.kind == "connection_error"


@pytest.mark.parametrize("body", [b"not json", b"[]", b'{"answers": {}}', b'{"answers": [], "usage": {}}'])
def test_an_unreadable_answer_is_a_bad_response(body: bytes) -> None:
    adapter, _ = client(HttpResponse(200, body))
    with pytest.raises(ClientError) as failure:
        adapter.call("complete", request())
    assert failure.value.kind == "bad_response"


def test_a_missing_answer_for_a_question_is_a_bad_response() -> None:
    body = json.loads(fixture("openrouter_decisions_ok.json").body)
    del body["answers"]["injection"]
    adapter, _ = client(HttpResponse(200, json.dumps(body).encode()))
    with pytest.raises(ClientError) as failure:
        adapter.call("complete", request())
    assert failure.value.kind == "bad_response"
    assert failure.value.usage == Tokens("openrouter", "jev-1.14", 412, 6)


def test_only_the_complete_operation_and_a_known_model_are_served() -> None:
    adapter, transport = client()
    with pytest.raises(ClientError) as other:
        adapter.call("embed", request())
    assert other.value.kind == "unsupported_operation"
    unknown = CompletionRequest("jev-9", "x", None, False, Verdict.model_json_schema())
    with pytest.raises(ClientError) as model:
        adapter.call("complete", unknown)
    assert model.value.kind == "unknown_model"
    with pytest.raises(ClientError) as shape:
        adapter.call("complete", "just a string")
    assert shape.value.kind == "bad_request"
    assert transport.requests == []


def test_estimate_counts_the_prompt_and_prices_in_the_budget_table() -> None:
    adapter, _ = client()
    short = adapter.estimate("complete", request("x"))
    long = adapter.estimate("complete", request("x" * 3000))
    assert isinstance(short, Tokens) and isinstance(long, Tokens)
    assert (short.service, short.model) == ("openrouter", "jev-1.14")
    assert long.input >= short.input + 900
    assert long.output == short.output
    assert Decimal(0) < Decimal(long.input)


def test_the_key_is_never_in_the_adapter_repr() -> None:
    adapter, _ = client()
    assert KEY not in repr(adapter) and KEY not in str(adapter.__dict__)
