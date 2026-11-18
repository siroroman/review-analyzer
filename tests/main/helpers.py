import json
import re
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlsplit

from app.domain import FakeClock
from app.transport import HttpRequest, HttpResponse

FIXTURES = Path(__file__).parents[1] / "adapters" / "fixtures"
GOOGLE_ITEMS = Path(__file__).parents[1] / "fixtures/sources/google_maps/2026-11-17-yasogan-sample.json"
START = datetime(2026, 11, 13, 8, 0, tzinfo=UTC)
PLACE_ID = "ChIJ_RjZFHvsC0cRk0DRRqTuJlA"  # the id in google_places_details_ok.json
ACCESS_TOKEN = "metadata-token-value"  # noqa: S105 - a test value
TOPICS = ("staff", "waiting", "prices", "food", "place", "cleanliness", "quality", "other")

# Every secret and setting of `app.main`, with a value that is not a real one.
ENVIRON = {
    "DEMO_TOKENS": "demo-token-1",
    "ADMIN_TOKEN": "admin-token-1",
    "DATABASE_URL": "postgresql://user:db-secret@localhost/none",
    "GOOGLE_PLACES_API_KEY": "google-secret",
    "YASOGAN_URL": "https://yasogan.example",
    "OPENROUTER_API_KEY": "openrouter-secret",
    "LANGFUSE_PUBLIC_KEY": "langfuse-public",
    "LANGFUSE_SECRET_KEY": "langfuse-secret",
    "LANGFUSE_HOST": "https://langfuse.example",
    "CLOUD_TASKS_PROJECT": "review-analyzer",
    "CLOUD_TASKS_LOCATION": "europe-west1",
    "CLOUD_TASKS_QUEUE": "runs",
    "WORKER_URL": "https://worker.example/tasks/run",
    "WORKER_SERVICE_ACCOUNT": "worker@review-analyzer.iam.example",
}


def clock() -> FakeClock:
    return FakeClock(START)


def _json(body: object, status: int = 200) -> HttpResponse:
    return HttpResponse(status, json.dumps(body).encode())


def _file(name: str, status: int = 200) -> HttpResponse:
    return HttpResponse(status, (FIXTURES / name).read_bytes())


def scraped_items(count: int = 40) -> list[dict[str, object]]:
    """Scraper output in the shape of the recorded sample, with new ids so there are enough for a Taxonomy."""
    template = json.loads(GOOGLE_ITEMS.read_text())[0]
    day_ms = 86_400_000
    return [
        {
            **template,
            "review_id": f"review-{index:03d}",
            "time": {"published": str(1_792_000_000_000 + index * day_ms), "last_edited": None},
            "review": {"rating": 4, "text": f"Dobrá obsluha číslo {index}", "language": None},
        }
        for index in range(count)
    ]


def _model_answer(request: HttpRequest) -> HttpResponse:
    """DeepSeek (chat completions) for Topics, industry and insights; Jev (Decisions) for a Review."""
    body = json.loads(request.body)
    if request.url.endswith("/decisions"):
        return _json(_jev_answer(body["questions"]))
    system = body["messages"][0]["content"]
    prompt = body["messages"][1]["content"]
    answer: dict[str, object]
    if "sort public customer reviews" in system:
        count = len(json.loads(prompt.split("<reviews>")[1].split("</reviews>")[0]))
        topic = {
            "key": "staff",
            "name": "Obsluha",
            "description": "Obsluha",
            "reviews": list(range(1, count + 1)),
        }
        answer = {"topics": [topic]}
    elif "design a list of Topics" in system:
        answer = {"topics": [{"key": key, "name": key.title(), "description": key} for key in TOPICS]}
    elif "name the industry" in system:
        answer = {"label": "Hypermarket"}
    else:
        first = re.search(r'<review id="([^"]+)"', prompt)
        answer = {
            "insights": [
                {
                    "type": "summary",
                    "period_start": "2026-10-01",
                    "period_end": "2026-10-31",
                    "text": "Hosté chválí obsluhu.",
                    "review_ids": [first.group(1)] if first else [],
                }
            ]
        }
    return _json(
        {
            "choices": [
                {"finish_reason": "stop", "message": {"role": "assistant", "content": json.dumps(answer)}}
            ],
            "usage": {"prompt_tokens": 100, "completion_tokens": 20},
        }
    )


def _jev_answer(questions: dict[str, dict[str, object]]) -> dict[str, object]:
    """Every Review is about the staff, positively: a high score for `staff`, a low one for the rest."""
    answers: dict[str, object] = {}
    for name, question in questions.items():
        if question["type"] == "choice":
            answers[name] = {"type": "choice", "choice": "positive", "confidence": 0.9}
        else:
            answers[name] = {"type": "noul", "noul": 0.9 if name == "topic_staff" else 0.1, "confidence": 0.9}
    return {"answers": answers, "usage": {"input_tokens": 100, "output_tokens": 5}}


class Internet:
    """An `HttpTransport` that plays every service by its URL: Google, the scraper, OpenRouter, Langfuse,
    Cloud Tasks and the metadata server. It remembers every request; nothing leaves the process."""

    def __init__(self) -> None:
        self.requests: list[HttpRequest] = []
        self.tasks: list[dict[str, object]] = []

    def send(self, request: HttpRequest) -> HttpResponse:
        self.requests.append(request)
        url = request.url
        host = urlsplit(url).hostname
        if host == "metadata.google.internal":
            return _json({"access_token": ACCESS_TOKEN, "expires_in": 3599})
        if host == "places.googleapis.com":
            return _file(
                "google_places_autocomplete_ok.json"
                if "autocomplete" in url
                else "google_places_details_ok.json"
            )
        if host == "yasogan.example":
            return _json(scraped_items())
        if host == "openrouter.ai":
            return _model_answer(request)
        if host == "cloudtasks.googleapis.com":
            self.tasks.append(json.loads(request.body)["task"])
            return _json({})
        if host == "langfuse.example":
            return _file("langfuse_ingestion_207.json", 207)
        raise AssertionError(f"unexpected request to {url}")

    def hosts(self) -> set[str]:
        return {urlsplit(request.url).hostname or "" for request in self.requests}
