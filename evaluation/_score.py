"""Accuracy of classification against the expected Topics.

For every Topic (counted over the whole set):
- recall: of the Reviews that expect the Topic, the share that got it;
- precision: of the Reviews that got the Topic, the share that expects it;
- sentiment accuracy: of the Reviews that got an expected Topic, the share with the expected sentiment
  (`unclassified` has no sentiment of its own and is left out of it).
A value is `None` when its denominator is 0. The overall sentiment accuracy pools all found Topics.
`unclassified_share` is the share of Reviews whose answer is only `unclassified` (or missing).
"""

from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass

from app.domain import ReviewTopic
from app.taxonomy import UNCLASSIFIED_KEY
from evaluation._data import SetItem


def _ratio(part: int, whole: int) -> float | None:
    return part / whole if whole else None


@dataclass
class TopicScore:
    expected: int = 0  # Reviews that expect the Topic
    predicted: int = 0  # Reviews that got the Topic
    found: int = 0  # both
    rated: int = 0  # found, and with a sentiment of its own (not `unclassified`)
    sentiment_right: int = 0  # rated, with the expected sentiment

    @property
    def recall(self) -> float | None:
        return _ratio(self.found, self.expected)

    @property
    def precision(self) -> float | None:
        return _ratio(self.found, self.predicted)

    @property
    def sentiment_accuracy(self) -> float | None:
        return _ratio(self.sentiment_right, self.rated)


@dataclass
class Scores:
    reviews: int
    topics: dict[str, TopicScore]
    sentiment_accuracy: float | None
    unclassified_share: float


def score(items: Sequence[SetItem], actual: Sequence[ReviewTopic]) -> Scores:
    """Compare the answers (`review_external_id` is the id of a set item) with what a person expects."""
    answers: dict[str, dict[str, ReviewTopic]] = defaultdict(dict)
    for topic in actual:
        answers[topic.review_external_id][topic.topic_key] = topic
    topics: dict[str, TopicScore] = defaultdict(TopicScore)
    found = 0
    right = 0
    unclassified = 0
    for entry in items:
        got = answers.get(entry.id, {})
        if set(got) <= {UNCLASSIFIED_KEY}:
            unclassified += 1
        for key in got:
            topics[key].predicted += 1
        for expected in entry.expected:
            topics[expected.topic].expected += 1
            match = got.get(expected.topic)
            if match is None:
                continue
            topics[expected.topic].found += 1
            if expected.topic == UNCLASSIFIED_KEY:
                continue  # always neutral: it would only inflate sentiment accuracy
            topics[expected.topic].rated += 1
            found += 1
            if match.sentiment == expected.sentiment:
                topics[expected.topic].sentiment_right += 1
                right += 1
    return Scores(
        reviews=len(items),
        topics=dict(sorted(topics.items())),
        sentiment_accuracy=_ratio(right, found),
        unclassified_share=unclassified / len(items) if items else 0.0,
    )
