import json

import pytest
from pydantic import SecretStr

from app.gateway import AnthropicClient, ClientError, ClientTimeout, Tokens
from app.llm import CompletionRequest
from app.transport import FakeTransport, HttpError, HttpResponse, HttpTimeout
from tests.adapters.helpers import Verdict, body_of, fixture

KEY = "sk-ant-secret-5678"
MODELS = {"claude-haiku": "claude-haiku-5-5", "claude-sonnet": "claude-sonnet-5-5"}


def client(*steps: HttpResponse | HttpError) -> tuple[AnthropicClient, FakeTransport]:
    transport = FakeTransport(*steps)
    return AnthropicClient(SecretStr(KEY), transport, MODELS, max_output_tokens=2048), transport


def request(
    model: str = "claude-haiku", system: str | None = "Classify the review.", cache: bool = False
) -> CompletionRequest:
    return CompletionRequest(
        model, "<review id=1>Pokoj byl špinavý.</review>", system, cache, Verdict.model_json_schema()
    )


def test_the_text_is_returned_and_all_input_tokens_are_counted() -> None:
    adapter, _ = client(fixture("anthropic_messages_ok.json"))
    response = adapter.call("complete", request())
    assert response.payload == '{"sentiment": "negative", "injection": false}'
    # 120 plain + 30 written to the cache + 50 read from it, all billed as input (an upper bound).
    assert response.usage == Tokens("anthropic", "claude-haiku", 200, 14)


def test_sends_the_messages_request_with_the_api_model_and_the_schema() -> None:
    adapter, transport = client(fixture("anthropic_messages_ok.json"))
    adapter.call("complete", request())
    sent = transport.requests[0]
    assert sent.url == "https://api.anthropic.com/v1/messages"
    assert sent.headers["x-api-key"] == KEY
    assert sent.headers["anthropic-version"] == "2023-06-01"
    body = body_of(sent.body)
    assert body["model"] == "claude-haiku-5-5"
    assert body["max_tokens"] == 2048
    assert body["messages"] == [{"role": "user", "content": "<review id=1>Pokoj byl špinavý.</review>"}]
    system = body["system"]
    assert isinstance(system, list) and len(system) == 1
    assert system[0]["text"].startswith("Classify the review.")
    assert json.dumps(Verdict.model_json_schema()) in system[0]["text"]
    assert "cache_control" not in system[0]


def test_prompt_caching_marks_the_system_block() -> None:
    adapter, transport = client(fixture("anthropic_messages_ok.json"))
    adapter.call("complete", request(cache=True))
    system = body_of(transport.requests[0].body)["system"]
    assert isinstance(system, list)
    assert system[0]["cache_control"] == {"type": "ephemeral"}


def test_without_a_system_prompt_the_schema_instruction_still_goes() -> None:
    adapter, transport = client(fixture("anthropic_messages_ok.json"))
    adapter.call("complete", request(system=None))
    system = body_of(transport.requests[0].body)["system"]
    assert isinstance(system, list)
    assert "JSON" in system[0]["text"]


def test_a_cut_off_answer_fails_and_charges_the_tokens_used() -> None:
    adapter, _ = client(fixture("anthropic_messages_truncated.json"))
    with pytest.raises(ClientError) as failure:
        adapter.call("complete", request())
    assert failure.value.kind == "truncated"
    assert failure.value.usage == Tokens("anthropic", "claude-haiku", 100, 4096)


@pytest.mark.parametrize(
    ("status", "kind"),
    [
        (429, "rate_limited"),
        (529, "server_error"),
        (500, "server_error"),
        (401, "auth"),
        (400, "bad_request"),
    ],
)
def test_an_error_status_is_a_client_error_of_a_short_kind(status: int, kind: str) -> None:
    adapter, _ = client(fixture("anthropic_error_overloaded.json", status))
    with pytest.raises(ClientError) as failure:
        adapter.call("complete", request())
    assert failure.value.kind == kind
    assert failure.value.usage is None
    assert "Overloaded" not in str(failure.value)


def test_timeout_and_dropped_connection() -> None:
    adapter, _ = client(HttpTimeout("timeout"), HttpError("connection failed"))
    with pytest.raises(ClientTimeout):
        adapter.call("complete", request())
    with pytest.raises(ClientError) as failure:
        adapter.call("complete", request())
    assert failure.value.kind == "connection_error"


@pytest.mark.parametrize(
    "body",
    [
        b"nope",
        b"[]",
        b'{"content": [], "usage": {"input_tokens": 1, "output_tokens": 1}}',
        b'{"content": [{"type": "text", "text": "x"}]}',
        b'{"content": [{"type": "text", "text": "x"}], "usage": {"input_tokens": "1", "output_tokens": 1}}',
    ],
)
def test_an_unreadable_answer_is_a_bad_response(body: bytes) -> None:
    adapter, _ = client(HttpResponse(200, body))
    with pytest.raises(ClientError) as failure:
        adapter.call("complete", request())
    assert failure.value.kind == "bad_response"


def test_unknown_model_operation_and_shape_make_no_call() -> None:
    adapter, transport = client()
    for operation, asked, kind in [
        ("complete", request("claude-opus"), "unknown_model"),
        ("embed", request(), "unsupported_operation"),
        ("complete", "text", "bad_request"),
    ]:
        with pytest.raises(ClientError) as failure:
            adapter.call(operation, asked)
        assert failure.value.kind == kind
    assert transport.requests == []


def test_estimate_is_priced_by_model_and_leaves_room_for_the_whole_answer() -> None:
    adapter, _ = client()
    estimate = adapter.estimate("complete", request("claude-sonnet"))
    assert isinstance(estimate, Tokens)
    assert (estimate.service, estimate.model, estimate.output) == ("anthropic", "claude-sonnet", 2048)
    assert estimate.input >= len(request().prompt) // 3


def test_the_key_is_never_in_the_adapter_repr() -> None:
    adapter, _ = client()
    assert KEY not in repr(adapter) and KEY not in str(adapter.__dict__)
