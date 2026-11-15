from datetime import UTC, datetime

from app.domain import ReviewTopic, Sentiment
from evaluation import DROP_THRESHOLD, Expected, Report, SetItem, build_report, render, score

NOW = datetime(2026, 11, 15, 8, 0, tzinfo=UTC)


def report(food_recall_found: bool, sentiment: str = "positive") -> Report:
    items = [SetItem("e001", "t", None, None, (Expected("food", Sentiment.POSITIVE),))]
    actual = (
        [
            ReviewTopic(
                review_external_id="e001", topic_key="food", sentiment=Sentiment(sentiment), confidence=1
            )
        ]
        if food_recall_found
        else []
    )
    return build_report(score(items, actual), taxonomy_version=2, taken_at=NOW, models="jev-1.14")


def test_report_round_trips_through_json_and_holds_no_review_text() -> None:
    original = report(True)

    text = original.to_json()

    assert Report.from_json(text) == original
    assert '"t"' not in text and "text" not in text  # numbers only
    assert original.taxonomy_version == 2 and original.reviews == 1 and original.taken_at == NOW


def test_render_without_a_last_report_shows_the_numbers_only() -> None:
    out = render(report(True), None)

    assert "food" in out and "recall 100%" in out
    assert "no earlier report" in out


def test_render_shows_the_change_against_the_last_report() -> None:
    out = render(report(False), report(True))

    assert "recall 0% (-100 pp)" in out  # percentage points
    assert "DROP" in out


def test_a_small_change_is_not_a_drop() -> None:
    assert DROP_THRESHOLD == 0.05
    out = render(report(True), report(True))

    assert "DROP" not in out and "(+0 pp)" in out


def test_a_new_sentiment_mistake_is_shown_as_a_drop() -> None:
    out = render(report(True, "negative"), report(True))

    assert "sentiment accuracy 0% (-100 pp)" in out and "DROP" in out
