import json
import re
from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, create_model

from app.domain import Review, ReviewTopic, Sentiment, Source
from app.gateway import ClientError
from app.llm import InvalidOutput, Llm
from app.storage import ReviewRepo, StoredTaxonomy
from app.taxonomy import UNCLASSIFIED_KEY

TASK = "classification"
MAX_TOPICS_PER_REVIEW = 3
# A Topic whose score is below this is not assigned. A first guess, to be calibrated on labelled Reviews.
MIN_SCORE = 0.5
_UNSAFE = re.compile(r"[^a-z0-9_]")


@dataclass(frozen=True)
class ClassificationResult:
    """How many Reviews got real Topics and how many ended as `unclassified`."""

    classified: int
    unclassified: int


class _Judgement(BaseModel):
    """The base of the answer schema of one Review: a score and a sentiment for every Topic."""

    model_config = ConfigDict(extra="forbid")


@dataclass(frozen=True)
class _Fields:
    """The names of the two answer fields of one Topic."""

    key: str
    score: str
    sentiment: str


def _schema(taxonomy: StoredTaxonomy) -> tuple[type[BaseModel], list[_Fields]]:
    """The answer schema of a Taxonomy and which fields belong to which Topic key.

    Two questions per Topic: a score from 0 to 1 (the description of the Topic is its criteria) and the
    sentiment about that Topic. `unclassified` is not asked: code assigns it.
    """
    fields: dict[str, object] = {}
    asked: list[_Fields] = []
    for topic in taxonomy.taxonomy.topics:
        if topic.key == UNCLASSIFIED_KEY:
            continue
        slug = _UNSAFE.sub("_", topic.key.lower())
        names = _Fields(topic.key, f"topic_{slug}", f"sentiment_{slug}")
        asked.append(names)
        fields[names.score] = (float, Field(description=topic.description))
        fields[names.sentiment] = (Literal["positive", "neutral", "negative"], ...)
    model = create_model("Judgement", __base__=_Judgement, **fields)  # type: ignore[call-overload]
    return model, asked


def _prompt(review: Review) -> str:
    # json.dumps escapes quotes and newlines; "<" is escaped too so no text can close the delimiter.
    text = json.dumps(review.text, ensure_ascii=False).replace("<", "\\u003c")
    return f"<review>\n{text}\n</review>"


class Classifier:
    """Gives every Review of a Place Topics for one Taxonomy version, once."""

    def __init__(self, llm: Llm, reviews: ReviewRepo) -> None:
        self._llm = llm
        self._reviews = reviews

    def classify(
        self, source: Source, place_external_id: str, taxonomy: StoredTaxonomy, *, run_id: str
    ) -> ClassificationResult:
        """Classify the Reviews of the Place that have no ReviewTopic for this Taxonomy version yet.

        One model call per Review, saved as soon as it is done. A Review the model failed on, or that
        scored below `MIN_SCORE` on every Topic, gets the Topic `unclassified` and is counted. Reviews
        without text and Flagged Reviews are never sent.
        """
        todo = [
            r
            for r in self._reviews.unclassified(source, place_external_id, taxonomy)
            if r.has_text and not r.flagged
        ]
        schema, asked = _schema(taxonomy)
        classified = 0
        unclassified = 0
        for review in todo:
            topics = self._judge(review, schema, asked, run_id)
            if topics:
                classified += 1
            else:
                topics = [_unclassified(review)]
                unclassified += 1
            self._reviews.save_topics(source, taxonomy, topics)
        return ClassificationResult(classified, unclassified)

    def _judge(
        self, review: Review, schema: type[BaseModel], asked: list[_Fields], run_id: str
    ) -> list[ReviewTopic]:
        try:
            answer = self._llm.complete(TASK, _prompt(review), schema, run_id=run_id)
        except (InvalidOutput, ClientError):
            # `llm` already retried. BudgetExceeded and GatewayDenied are not caught here: they stop the run.
            return []
        values = answer.model_dump()
        found = sorted(
            (
                (values[names.score], names.key, Sentiment(values[names.sentiment]))
                for names in asked
                if MIN_SCORE <= values[names.score] <= 1
            ),
            key=lambda item: item[0],
            reverse=True,
        )
        return [
            ReviewTopic(
                review_external_id=review.external_id, topic_key=key, sentiment=sentiment, confidence=score
            )
            for score, key, sentiment in found[:MAX_TOPICS_PER_REVIEW]
        ]


def _unclassified(review: Review) -> ReviewTopic:
    return ReviewTopic(
        review_external_id=review.external_id,
        topic_key=UNCLASSIFIED_KEY,
        sentiment=Sentiment.NEUTRAL,
        confidence=0,
    )
