import json

import pytest
from pydantic import SecretStr

from app.gateway import ClientError, ClientTimeout, OpenRouterChatClient, Tokens
from app.llm import CompletionRequest
from app.transport import FakeTransport, HttpError, HttpResponse, HttpTimeout
from tests.adapters.helpers import Verdict, body_of, fixture

KEY = "sk-or-secret-9999"
MODELS = {"deepseek-v4.1-flash": "deepseek/deepseek-v4.1-flash"}
PROMPT = '<reviews>\n["Pokoj byl špinavý."]\n</reviews>'


def client(*steps: HttpResponse | HttpError) -> tuple[OpenRouterChatClient, FakeTransport]:
    transport = FakeTransport(*steps)
    return OpenRouterChatClient(SecretStr(KEY), transport, MODELS, max_output_tokens=2048), transport


def request(
    model: str = "deepseek-v4.1-flash", system: str | None = "Name the sentiment."
) -> CompletionRequest:
    return CompletionRequest(model, PROMPT, system, False, Verdict.model_json_schema())


def test_the_text_is_returned_with_the_usage_of_the_provider() -> None:
    adapter, _ = client(fixture("openrouter_chat_ok.json"))
    response = adapter.call("complete", request())
    assert response.payload == '{"sentiment": "negative", "injection": false}'
    assert response.usage == Tokens("openrouter_chat", "deepseek-v4.1-flash", 180, 14)


def test_sends_a_chat_completion_with_the_api_model_the_system_prompt_and_the_schema() -> None:
    adapter, transport = client(fixture("openrouter_chat_ok.json"))
    adapter.call("complete", request())
    sent = transport.requests[0]
    assert sent.method == "POST"
    assert sent.url == "https://openrouter.ai/api/v1/chat/completions"
    assert sent.headers["Authorization"] == f"Bearer {KEY}"
    body = body_of(sent.body)
    assert body["model"] == "deepseek/deepseek-v4.1-flash"
    assert body["max_tokens"] == 2048
    assert body["response_format"] == {"type": "json_object"}
    messages = body["messages"]
    assert isinstance(messages, list) and len(messages) == 2
    system, user = messages
    assert system["role"] == "system"
    assert system["content"].startswith("Name the sentiment.")
    assert json.dumps(Verdict.model_json_schema()) in system["content"]
    assert user == {"role": "user", "content": PROMPT}


def test_without_a_system_prompt_the_schema_instruction_still_goes() -> None:
    adapter, transport = client(fixture("openrouter_chat_ok.json"))
    adapter.call("complete", request(system=None))
    system = body_of(transport.requests[0].body)["messages"][0]  # type: ignore[index]
    assert "JSON" in system["content"]


def test_a_cut_off_answer_fails_and_charges_the_tokens_used() -> None:
    adapter, _ = client(fixture("openrouter_chat_truncated.json"))
    with pytest.raises(ClientError) as failure:
        adapter.call("complete", request())
    assert failure.value.kind == "truncated"
    assert failure.value.usage == Tokens("openrouter_chat", "deepseek-v4.1-flash", 100, 4096)


@pytest.mark.parametrize(
    ("status", "kind"),
    [(429, "rate_limited"), (500, "server_error"), (401, "auth"), (402, "payment"), (400, "bad_request")],
)
def test_an_error_status_is_a_client_error_of_a_short_kind(status: int, kind: str) -> None:
    adapter, _ = client(fixture("openrouter_chat_error.json", status))
    with pytest.raises(ClientError) as failure:
        adapter.call("complete", request())
    assert failure.value.kind == kind
    assert failure.value.usage is None
    assert "secret provider detail" not in str(failure.value)


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
        b'{"choices": [], "usage": {"prompt_tokens": 1, "completion_tokens": 1}}',
        b'{"choices": [{"finish_reason": "stop", "message": {"content": "x"}}]}',
        b'{"choices": [{"finish_reason": "stop", "message": {"content": null}}], '
        b'"usage": {"prompt_tokens": 1, "completion_tokens": 1}}',
        b'{"choices": [{"finish_reason": "stop", "message": {"content": "x"}}], '
        b'"usage": {"prompt_tokens": "1", "completion_tokens": 1}}',
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
        ("complete", request("deepseek-v9"), "unknown_model"),
        ("embed", request(), "unsupported_operation"),
        ("complete", "text", "bad_request"),
    ]:
        with pytest.raises(ClientError) as failure:
            adapter.call(operation, asked)
        assert failure.value.kind == kind
    assert transport.requests == []


def test_estimate_is_priced_by_model_and_leaves_room_for_the_whole_answer() -> None:
    adapter, _ = client()
    estimate = adapter.estimate("complete", request())
    assert isinstance(estimate, Tokens)
    assert (estimate.service, estimate.model, estimate.output) == (
        "openrouter_chat",
        "deepseek-v4.1-flash",
        2048,
    )
    assert estimate.input >= len(PROMPT) // 3


def test_the_key_is_never_in_the_adapter_repr() -> None:
    adapter, _ = client()
    assert KEY not in repr(adapter) and KEY not in str(adapter.__dict__)


def test_a_non_positive_output_limit_is_refused() -> None:
    with pytest.raises(ValueError, match="max_output_tokens"):
        OpenRouterChatClient(SecretStr(KEY), FakeTransport(), MODELS, max_output_tokens=0)
