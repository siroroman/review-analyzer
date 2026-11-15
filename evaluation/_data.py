"""The evaluation set: hand-labelled, anonymized Reviews with the Topics a person expects for each."""

import json
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.domain import DatePrecision, RawReview, Sentiment, Source, Taxonomy, Topic
from app.sanitize import PatternInjectionDetector, prepare
from app.taxonomy import UNCLASSIFIED_KEY

MAX_EXPECTED = 3  # the most Topics `classification` keeps per Review
_ID = re.compile(r"e\d{3,}")


class InvalidSet(ValueError):
    """The set breaks the format or the anonymization rules; the message names the line and the id."""


@dataclass(frozen=True)
class Expected:
    """One Topic a person expects for a Review, with its sentiment."""

    topic: str
    sentiment: Sentiment


@dataclass(frozen=True)
class SetItem:
    id: str
    text: str
    rating: int | None
    language: str | None
    expected: tuple[Expected, ...]


@dataclass(frozen=True)
class EvaluationSet:
    """The Reviews and the Taxonomy they were labelled against."""

    items: tuple[SetItem, ...]
    taxonomy: Taxonomy


class _Expected(BaseModel):
    model_config = ConfigDict(extra="forbid")

    topic: str
    sentiment: Sentiment


class _Row(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    text: str
    rating: Annotated[int, Field(ge=1, le=5)] | None = None
    language: str | None = None
    expected: list[_Expected]


def load_set(reviews: Path, taxonomy: Path) -> EvaluationSet:
    """Read and check the set. Raises `InvalidSet` on the first row that is not usable."""
    loaded = _load_taxonomy(taxonomy)
    keys = {topic.key for topic in loaded.topics}
    items: list[SetItem] = []
    seen: set[str] = set()
    lines = reviews.read_text(encoding="utf-8").splitlines()
    for number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            row = _Row.model_validate_json(line)
        except ValidationError as error:
            raise InvalidSet(f"line {number}{_id_of(line)}: {_first_problem(line, error)}") from error
        if row.id in seen:
            raise InvalidSet(f"line {number}: id {row.id} is used twice")
        seen.add(row.id)
        problem = _row_problem(row, keys)
        if problem:
            raise InvalidSet(f"line {number}, {row.id}: {problem}")
        items.append(
            SetItem(
                row.id,
                row.text,
                row.rating,
                row.language,
                tuple(Expected(e.topic, e.sentiment) for e in row.expected),
            )
        )
    if not items:
        raise InvalidSet(f"{reviews} is empty")
    return EvaluationSet(tuple(items), loaded)


def _id_of(line: str) -> str:
    try:
        parsed = json.loads(line)
    except ValueError:
        return ""
    return f", {parsed['id']}" if isinstance(parsed, dict) and isinstance(parsed.get("id"), str) else ""


def _first_problem(line: str, error: ValidationError) -> str:
    try:
        json.loads(line)
    except ValueError:
        return "not valid JSON"
    first = error.errors()[0]
    return f"{'.'.join(str(part) for part in first['loc'])}: {first['msg']}"


def _load_taxonomy(path: Path) -> Taxonomy:
    try:
        raw = Taxonomy.model_validate(json.loads(path.read_text(encoding="utf-8")), strict=False)
    except (ValueError, ValidationError) as error:
        raise InvalidSet(f"{path}: not a Taxonomy ({error})") from error
    if any(topic.key == UNCLASSIFIED_KEY for topic in raw.topics):
        return raw
    # Stored Taxonomies always end with the reserved Topic (`taxonomy` adds it); the file may leave it out.
    unclassified = Topic(
        key=UNCLASSIFIED_KEY, name="Unclassified", description="Reviews that fit none of the other Topics."
    )
    return Taxonomy(industry=raw.industry, topics=(*raw.topics, unclassified))


def _row_problem(row: _Row, keys: set[str]) -> str | None:
    if not _ID.fullmatch(row.id):
        return "id must look like e001 (a new number, never a Source id)"
    if not row.text.strip():
        return "text is empty"
    if not 1 <= len(row.expected) <= MAX_EXPECTED:
        return f"expected must hold 1 to {MAX_EXPECTED} Topics "
    topics = [e.topic for e in row.expected]
    if len(set(topics)) != len(topics):
        return "a Topic is expected twice"
    unknown = sorted(set(topics) - keys)
    if unknown:
        return f"unknown Topic {', '.join(unknown)}"
    return _anonymization_problem(row)


def _anonymization_problem(row: _Row) -> str | None:
    """The text must survive `sanitize` unchanged: no contacts, hidden characters or injection patterns."""
    raw = RawReview(
        source=Source.GOOGLE_MAPS,
        place_external_id="evaluation",
        external_id=row.id,
        rating=row.rating or 3,
        text=row.text,
        published_on=date(2026, 1, 1),
        date_precision=DatePrecision.DAY,
        language=row.language,
    )
    prepared = prepare([raw], PatternInjectionDetector())
    if prepared.flagged:
        return "text is Flagged by sanitize (looks like an instruction to a model); anonymize or remove it"
    if not prepared.clean or prepared.clean[0].text != row.text:
        return "text changes under sanitize (contact, URL or hidden character): anonymize it by hand"
    return None
