"""The report of one evaluation: numbers only (never Review text), and its comparison with the last one."""

import json
from dataclasses import dataclass
from datetime import datetime

from evaluation._score import Scores

DROP_THRESHOLD = 0.05  # a fall of more than 5 percentage points is marked DROP


@dataclass(frozen=True)
class Report:
    taken_at: datetime
    taxonomy_version: int
    models: str
    reviews: int
    sentiment_accuracy: float | None
    unclassified_share: float
    # topic -> {"expected": n, "recall": x, "precision": x, "sentiment_accuracy": x}
    topics: dict[str, dict[str, float | None]]

    def to_json(self) -> str:
        data = {**self.__dict__, "taken_at": self.taken_at.isoformat()}
        return json.dumps(data, indent=2, sort_keys=True) + "\n"

    @staticmethod
    def from_json(text: str) -> "Report":
        data = json.loads(text)
        data["taken_at"] = datetime.fromisoformat(data["taken_at"])
        return Report(**data)


def build_report(scores: Scores, *, taxonomy_version: int, taken_at: datetime, models: str) -> Report:
    return Report(
        taken_at=taken_at,
        taxonomy_version=taxonomy_version,
        models=models,
        reviews=scores.reviews,
        sentiment_accuracy=scores.sentiment_accuracy,
        unclassified_share=scores.unclassified_share,
        topics={
            key: {
                "expected": topic.expected,
                "recall": topic.recall,
                "precision": topic.precision,
                "sentiment_accuracy": topic.sentiment_accuracy,
            }
            for key, topic in scores.topics.items()
        },
    )


def _cell(label: str, now: float | None, before: float | None, *, higher_is_better: bool = True) -> str:
    if now is None:
        return f"{label} n/a"
    text = f"{label} {now:.0%}"
    if before is None:
        return text
    delta = now - before
    text += f" ({delta * 100:+.0f} pp)"
    worse = -delta if higher_is_better else delta
    return text + (" DROP" if worse > DROP_THRESHOLD else "")


def render(report: Report, last: Report | None) -> str:
    """A table for the terminal; with `last`, every number shows its change in percentage points."""
    head = f"{report.reviews} Reviews, Taxonomy v{report.taxonomy_version}, {report.models}"
    lines = [head, ""]
    before = last.topics if last else {}
    for key, topic in report.topics.items():
        old = before.get(key, {})
        cells = [
            _cell("recall", topic["recall"], old.get("recall")),
            _cell("precision", topic["precision"], old.get("precision")),
            _cell("sentiment accuracy", topic["sentiment_accuracy"], old.get("sentiment_accuracy")),
        ]
        lines.append(f"{key:<16} expected {int(topic['expected'] or 0):>3}  " + "  ".join(cells))
    lines.append("")
    lines.append(
        _cell(
            "overall sentiment accuracy",
            report.sentiment_accuracy,
            last.sentiment_accuracy if last else None,
        )
    )
    lines.append(
        _cell(
            "unclassified share",
            report.unclassified_share,
            last.unclassified_share if last else None,
            higher_is_better=False,
        )
    )
    lines.append(
        f"compared with the report of {last.taken_at:%Y-%m-%d}" if last else "no earlier report to compare"
    )
    return "\n".join(lines)
