import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel

from app.transport import HttpResponse

FIXTURES = Path(__file__).parent / "fixtures"


class Verdict(BaseModel):
    sentiment: Literal["positive", "neutral", "negative"]
    injection: bool


def fixture(name: str, status: int = 200) -> HttpResponse:
    return HttpResponse(status, (FIXTURES / name).read_bytes())


def body_of(data: bytes) -> dict[str, object]:
    parsed = json.loads(data)
    assert isinstance(parsed, dict)
    return parsed
