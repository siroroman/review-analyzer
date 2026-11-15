from app.domain import ReviewTopic, Sentiment
from evaluation import Expected, SetItem, score


def item(id_: str, *expected: tuple[str, str]) -> SetItem:
    return SetItem(id_, "text", None, None, tuple(Expected(t, Sentiment(s)) for t, s in expected))


def got(id_: str, topic: str, sentiment: str) -> ReviewTopic:
    return ReviewTopic(
        review_external_id=id_, topic_key=topic, sentiment=Sentiment(sentiment), confidence=0.9
    )


ITEMS = [
    item("e001", ("staff", "positive"), ("waiting", "negative")),
    item("e002", ("food", "positive")),
    item("e003", ("staff", "negative")),
]
ACTUAL = [
    got("e001", "staff", "positive"),
    got("e001", "prices", "neutral"),
    got("e002", "food", "negative"),
    got("e003", "staff", "negative"),
    got("e003", "waiting", "negative"),
]


def test_worked_example_per_topic() -> None:
    scores = score(ITEMS, ACTUAL)

    staff = scores.topics["staff"]
    assert (staff.expected, staff.predicted, staff.found, staff.sentiment_right) == (2, 2, 2, 2)
    assert (staff.recall, staff.precision, staff.sentiment_accuracy) == (1.0, 1.0, 1.0)

    waiting = scores.topics["waiting"]  # missed for e001, wrongly added for e003
    assert (waiting.recall, waiting.precision, waiting.sentiment_accuracy) == (0.0, 0.0, None)

    food = scores.topics["food"]  # found, but the sentiment is wrong
    assert (food.recall, food.precision, food.sentiment_accuracy) == (1.0, 1.0, 0.0)

    prices = scores.topics["prices"]  # never expected, predicted once
    assert (prices.recall, prices.precision) == (None, 0.0)


def test_worked_example_overall() -> None:
    scores = score(ITEMS, ACTUAL)

    assert scores.reviews == 3
    assert scores.sentiment_accuracy == 2 / 3  # 3 found Topics, 2 with the right sentiment
    assert scores.unclassified_share == 0.0


def test_a_review_answered_unclassified_is_counted() -> None:
    scores = score(
        [item("e001", ("food", "positive")), item("e002", ("food", "positive"))],
        [
            got("e001", "food", "positive"),
            got("e002", "unclassified", "neutral"),
        ],
    )

    assert scores.unclassified_share == 0.5
    assert scores.topics["food"].recall == 0.5


def test_no_found_topic_means_no_sentiment_accuracy() -> None:
    scores = score([item("e001", ("food", "positive"))], [])

    assert scores.sentiment_accuracy is None
    assert scores.unclassified_share == 1.0  # no answer at all
    assert scores.topics["food"].recall == 0.0
